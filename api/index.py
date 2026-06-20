import os
import sys
import json
import sqlite3
import concurrent.futures
from datetime import datetime, timezone
import requests
import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

# Add project root to sys.path to find the cloned finvizfinance package
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
finviz_dir = os.path.join(project_root, "finvizfinance")
if finviz_dir not in sys.path:
    sys.path.insert(0, finviz_dir)

from local_sync import SUPPORTED_SIGNALS, CUSTOM_FILTERS, SCREENER_COLUMNS, apply_signal_filter
from scoring_config import (
    DIMENSION_CAPS, TECH_FACTORS, FUND_FACTORS, SENT_FACTORS,
    VALUATION, RS_SCORING, MIN_SCORE, MIN_DIMENSIONS, LIQUIDITY_FLOOR
)

# Deferred imports for faster cold starts

app = FastAPI(title="US Stock Trading Opportunities API")

# Enable CORS for local testing
cors_origins = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

import redis

# Robust Cache implementation (Redis with local SQLite fallback)
class FallbackCache:
    def __init__(self):
        self.redis_url = os.environ.get("REDIS_URL") or os.environ.get("KV_URL") or os.environ.get("KV_REST_API_URL")
        self.is_redis = bool(self.redis_url)
        
        # Always resolve db path defensively for local fallback
        if os.environ.get("VERCEL") or not os.access(project_root, os.W_OK):
            self.db_path = "/tmp/cache.db"
            if not os.path.exists(self.db_path):
                import shutil
                packaged_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache.db")
                if os.path.exists(packaged_db):
                    try:
                        shutil.copy2(packaged_db, self.db_path)
                        print("Successfully copied packaged cache.db to /tmp/cache.db")
                    except Exception as copy_err:
                        print("Failed to copy packaged cache.db to /tmp/cache.db:", copy_err)
                else:
                    # Try project root fallback
                    packaged_db_root = os.path.join(project_root, "cache.db")
                    if os.path.exists(packaged_db_root):
                        try:
                            shutil.copy2(packaged_db_root, self.db_path)
                            print("Successfully copied packaged cache.db (root) to /tmp/cache.db")
                        except Exception as copy_err:
                            print("Failed to copy packaged cache.db (root) to /tmp/cache.db:", copy_err)
        else:
            self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache.db")
            if not os.path.exists(os.path.dirname(self.db_path)):
                self.db_path = os.path.join(project_root, "cache.db")

        if self.is_redis:
            try:
                if self.redis_url.startswith("http"):
                    self.is_redis_rest = True
                    self.kv_url = self.redis_url
                    self.kv_token = os.environ.get("KV_REST_API_TOKEN")
                else:
                    self.is_redis_rest = False
                    self.client = redis.from_url(self.redis_url, decode_responses=True)
            except Exception as e:
                print("Failed to connect to Redis, falling back to SQLite:", e)
                self.is_redis = False
                
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL;")
                cursor.execute("PRAGMA synchronous=NORMAL;")
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, expires_at INTEGER)"
                )
                conn.commit()
            self.cleanup_expired()
        except Exception as e:
            print("Failed to initialize SQLite cache:", e)

    def cleanup_expired(self):
        if not self.is_redis:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    now = int(datetime.now(timezone.utc).timestamp())
                    cursor.execute("DELETE FROM cache WHERE expires_at < ?", (now,))
                    conn.commit()
            except Exception as e:
                print("Failed to clean up expired SQLite cache:", e)


    def get(self, key: str):
        if self.is_redis:
            try:
                if getattr(self, "is_redis_rest", False):
                    headers = {"Authorization": f"Bearer {self.kv_token}"}
                    res = requests.get(f"{self.kv_url}/get/{key}", headers=headers, timeout=5)
                    if res.status_code == 200:
                        val = res.json().get("result")
                        if val:
                            return json.loads(val)
                else:
                    val = self.client.get(key)
                    if val:
                        return json.loads(val)
            except Exception as e:
                print("Redis cache get error:", e)
            
            # Redis key not found or failed, fallback to local SQLite cache
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM cache WHERE key = ?", (key,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    return json.loads(row[0])
            except Exception as sq_err:
                print("Redis-to-SQLite fallback cache get error:", sq_err)
            return None
        else:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT value, expires_at FROM cache WHERE key = ?", (key,))
                row = cursor.fetchone()
                conn.close()
                if row:
                    val, expires_at = row
                    if expires_at > int(datetime.now(timezone.utc).timestamp()):
                        return json.loads(val)
                    else:
                        # On Vercel, return stale data rather than deleting it and failing
                        if os.environ.get("VERCEL"):
                            print(f"Cache key '{key}' expired but returning stale data on Vercel.")
                            return json.loads(val)
                        self.delete(key)
            except Exception as e:
                print("SQLite cache get error:", e)
            return None

    def set(self, key: str, value: any, expires_in: int = 14400):  # 4 hours cache by default
        val_str = json.dumps(value)
        if self.is_redis:
            try:
                if getattr(self, "is_redis_rest", False):
                    headers = {"Authorization": f"Bearer {self.kv_token}"}
                    requests.post(f"{self.kv_url}/set/{key}?ex={expires_in}", headers=headers, data=val_str, timeout=5)
                else:
                    self.client.setex(key, expires_in, val_str)
            except Exception as e:
                print("Redis cache set error:", e)
        else:
            try:
                expires_at = int(datetime.now(timezone.utc).timestamp()) + expires_in
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                    (key, val_str, expires_at)
                )
                conn.commit()
                conn.close()
                self.cleanup_expired()
            except Exception as e:
                print("SQLite cache set error:", e)

    def delete(self, key: str):
        if self.is_redis:
            try:
                if getattr(self, "is_redis_rest", False):
                    headers = {"Authorization": f"Bearer {self.kv_token}"}
                    requests.post(f"{self.kv_url}/del/{key}", headers=headers, timeout=5)
                else:
                    self.client.delete(key)
            except Exception as e:
                print("Redis cache delete error:", e)
        else:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
                conn.close()
            except Exception as e:
                print("SQLite cache delete error:", e)

cache = FallbackCache()

@app.get("/api/health")
def health():
    return {"status": "ok", "vercel_kv": cache.is_redis}

@app.get("/api/sync")
def trigger_sync(background_tasks: BackgroundTasks, api_key: str = None):
    expected_key = os.environ.get("SYNC_API_KEY")
    # If SYNC_API_KEY is configured, enforce it. Otherwise, allow syncing without key by default.
    if expected_key and api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key.")
        
    from local_sync import run_all_sync
    background_tasks.add_task(run_all_sync)
    return {"status": "sync_triggered", "message": "Synchronization started in the background."}

@app.get("/api/opportunities")
def get_opportunities(signal: str = "Oversold"):
    cache_key = f"opps_{signal.lower().replace(' ', '_')}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"data": cached_data, "source": "cache", "updated_at": datetime.now(timezone.utc).isoformat()}

    normalized_signal = signal.lower().replace(" ", "_")
    if normalized_signal not in SUPPORTED_SIGNALS:
        raise HTTPException(
            status_code=400,
            detail=f"Signal '{signal}' not supported. Choose from {list(SUPPORTED_SIGNALS.keys())}"
        )

    try:
        from finvizfinance.screener.custom import Custom
        fcustom = Custom()
        apply_signal_filter(fcustom, normalized_signal, SUPPORTED_SIGNALS[normalized_signal])
            
        df = fcustom.screener_view(
            limit=100, 
            order="Market Cap.", 
            ascend=False, 
            verbose=0, 
            columns=SCREENER_COLUMNS
        )
        
        data = []
        if df is not None:
            df = df.fillna("")
            data = df.to_dict(orient="records")
            
        cache.set(cache_key, data, expires_in=7200) # 2 hours cache for screener
        return {"data": data, "source": "live", "updated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        print(f"[ERROR] opportunities: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch opportunities data.")

@app.get("/api/insiders")
def get_insiders(option: str = "top owner trade"):
    cache_key = f"insiders_{option.lower().replace(' ', '_')}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"data": cached_data, "source": "cache", "updated_at": datetime.now(timezone.utc).isoformat()}

    supported_options = ["latest", "top week", "top owner trade"]
    if option not in supported_options:
        raise HTTPException(
            status_code=400,
            detail=f"Option '{option}' not supported. Choose from {supported_options}"
        )

    try:
        from finvizfinance.insider import Insider
        finsider = Insider(option=option)
        df = finsider.get_insider()
        
        data = []
        if df is not None:
            # clean nan/none values for JSON
            df = df.fillna("")
            data = df.to_dict(orient="records")
            
        cache.set(cache_key, data, expires_in=7200) # 2 hours cache
        return {"data": data, "source": "live", "updated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        print(f"[ERROR] insiders: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch insider data.")

@app.get("/api/sectors")
def get_sectors():
    cache_key = "sectors_performance"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"data": cached_data, "source": "cache", "updated_at": datetime.now(timezone.utc).isoformat()}

    try:
        from finvizfinance.group.overview import Overview as GroupOverview
        fgoverview = GroupOverview()
        df = fgoverview.screener_view(group="Sector")
        
        data = []
        if df is not None:
            df = df.fillna("")
            data = df.to_dict(orient="records")
            
        cache.set(cache_key, data, expires_in=14400) # 4 hours cache
        return {"data": data, "source": "live", "updated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        print(f"[ERROR] sectors: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch sector data.")

@app.get("/api/sectors/{sector_name}")
def get_sector_details(sector_name: str):
    from urllib.parse import unquote
    sector_name = unquote(sector_name).strip()
    
    # 1. Load sectors performance to get specific sector metrics
    sectors_perf = cache.get("sectors_performance") or []
    sector_metric = next((s for s in sectors_perf if s.get("Name", "").lower() == sector_name.lower()), {})
    real_sector_name = sector_metric.get("Name") or sector_name
    
    # 2. Get industries performance
    industries_perf = cache.get("industries_performance") or []
    
    # 3. Get confluences
    confluences_response = get_confluences()
    confluences = confluences_response.get("data") or []
    
    # 4. Scan cached opportunities to get mapping of Sector -> Industries dynamically
    industries_in_sector = set()
    supported_signals = list(SUPPORTED_SIGNALS.keys())
    
    for s in confluences:
        if s.get("Sector", "").lower() == real_sector_name.lower():
            ind = s.get("Industry")
            if ind:
                industries_in_sector.add(ind)
                
    for sig in supported_signals:
        sig_data = cache.get(f"opps_{sig}") or []
        for s in sig_data:
            if s.get("Sector", "").lower() == real_sector_name.lower():
                ind = s.get("Industry")
                if ind:
                    industries_in_sector.add(ind)
                    
    # 5. Filter industries performance for this sector
    matched_industries = []
    for ind in industries_in_sector:
        perf = next((i for i in industries_perf if i.get("Name", "").lower() == ind.lower()), None)
        if perf:
            matched_industries.append(perf)
        else:
            matched_industries.append({"Name": ind, "Change": "0.0%", "Stocks": 0})
            
    def parse_pct(s):
        try:
            return float(str(s).replace("%", "").strip())
        except:
            return -999.0
    matched_industries = sorted(matched_industries, key=lambda x: parse_pct(x.get("Change", 0)), reverse=True)
    
    # 6. Filter top confluence stocks in this sector
    sector_confluences = [
        s for s in confluences 
        if s.get("Sector", "").lower() == real_sector_name.lower()
    ]
    
    return {
        "sector": real_sector_name,
        "metrics": sector_metric,
        "industries": matched_industries,
        "confluences": sector_confluences,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/reddit")
def get_reddit_sentiment():
    cache_key = "reddit_sentiment"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"data": cached_data, "source": "cache"}

    try:
        res = requests.get("https://apewisdom.io/api/v1.0/filter/all-stocks", timeout=10)
        if res.status_code == 200:
            payload = res.json()
            data = payload.get("results", [])
            cache.set(cache_key, data, expires_in=1800) # 30 minutes cache
            return {"data": data, "source": "live"}
        else:
            raise HTTPException(status_code=res.status_code, detail="Failed to fetch from ApeWisdom")
    except Exception as e:
        print(f"[ERROR] reddit: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch Reddit sentiment data.")

@app.get("/api/stock/{ticker}")
def get_stock(ticker: str):
    cache_key = f"stock_details_{ticker.lower()}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"data": cached_data, "source": "cache"}

    try:
        from finvizfinance.quote import finvizfinance
        stock = finvizfinance(ticker)
        if not stock.flag:
            raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found on FinViz.")
            
        scrapers = {
            "fundament": stock.ticker_fundament,
            "ratings_outer": stock.ticker_outer_ratings,
            "news": stock.ticker_news,
            "inside trader": stock.ticker_inside_trader,
            "description": stock.ticker_description,
            "peers": stock.ticker_peer,
            "etfs": stock.ticker_etf_holders
        }

        info = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(scrapers)) as executor:
            future_to_key = {executor.submit(func): key for key, func in scrapers.items()}
            for future in concurrent.futures.as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    info[key] = future.result()
                except Exception as err:
                    print(f"Error scraping {key} for {ticker}: {err}")
                    if key == "fundament":
                        info[key] = {}
                    elif key in ["peers", "etfs"]:
                        info[key] = []
                    elif key == "description":
                        info[key] = ""
                    else:
                        info[key] = None
        
        res_info = {
            "fundament": info.get("fundament") or {},
            "description": info.get("description") or "",
            "peers": info.get("peers") or [],
            "etfs": info.get("etfs") or [],
        }
        
        if info.get("ratings_outer") is not None:
            if isinstance(info["ratings_outer"], pd.DataFrame):
                df_ratings = info["ratings_outer"].copy().fillna("")
                if "Date" in df_ratings.columns:
                    df_ratings["Date"] = df_ratings["Date"].apply(lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x))
                res_info["ratings_outer"] = df_ratings.to_dict(orient="records")
            else:
                res_info["ratings_outer"] = []
        else:
            res_info["ratings_outer"] = []
            
        if info.get("news") is not None:
            if isinstance(info["news"], pd.DataFrame):
                df_news = info["news"].copy().fillna("")
                if "Date" in df_news.columns:
                    df_news["Date"] = df_news["Date"].apply(lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x))
                res_info["news"] = df_news.to_dict(orient="records")
            else:
                res_info["news"] = []
        else:
            res_info["news"] = []
            
        if info.get("inside trader") is not None:
            if isinstance(info["inside trader"], pd.DataFrame):
                df_insider = info["inside trader"].copy().fillna("")
                res_info["inside_trader"] = df_insider.to_dict(orient="records")
            else:
                res_info["inside_trader"] = []
        else:
            res_info["inside_trader"] = []
            
        cache.set(cache_key, res_info, expires_in=14400) # 4 hours cache for single stock data
        return {"data": res_info, "source": "live"}
    except Exception as e:
        print(f"[ERROR] stock {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch stock details.")

@app.get("/api/confluences")
def get_confluences():
    # Detect empty cache state
    if (cache.get("opps_oversold") is None or 
        cache.get("opps_double_bottom") is None or 
        cache.get("insiders_top_owner_trade") is None):
        return {"status": "empty", "message": "Cache is empty. Please run sync first.", "data": []}

    oversold = cache.get("opps_oversold") or []
    double_bottom = cache.get("opps_double_bottom") or []
    new_high = cache.get("opps_new_high") or []
    triangle_ascending = cache.get("opps_triangle_ascending") or []
    unusual_volume = cache.get("opps_unusual_volume") or []
    high_short_interest = cache.get("opps_high_short_interest") or []
    pullback = cache.get("opps_pullback") or []
    breakout_candidate = cache.get("opps_breakout_candidate") or []
    quality_compounder = cache.get("opps_quality_compounder") or []
    upgrades = cache.get("opps_upgrades") or []
    downgrades = cache.get("opps_downgrades") or []
    earnings_before = cache.get("opps_earnings_before") or []
    earnings_after = cache.get("opps_earnings_after") or []
    most_active = cache.get("opps_most_active") or []
    top_losers = cache.get("opps_top_losers") or []
    overbought = cache.get("opps_overbought") or []
    wedge_up = cache.get("opps_wedge_up") or []
    wedge_down = cache.get("opps_wedge_down") or []
    top_gainers = cache.get("opps_top_gainers") or []
    most_volatile = cache.get("opps_most_volatile") or []
    recent_insider_buying_signal = cache.get("opps_recent_insider_buying") or []
    
    insiders = cache.get("insiders_top_owner_trade") or []
    insiders_latest = cache.get("insiders_latest") or []
    insiders_top_week = cache.get("insiders_top_week") or []
    
    reddit = cache.get("reddit_sentiment") or []
    sectors = cache.get("sectors_performance") or []

    def normalize_change_pct(val):
        """Normalize Change value to a percentage float.
        Handles both '5.00%' string and 0.05 decimal formats."""
        if val is None or val == '':
            return 0.0
        try:
            s = str(val).strip()
            if '%' in s:
                return float(s.replace('%', ''))
            else:
                return float(s) * 100
        except:
            return 0.0

    tickers_map = {}

    def get_field(item, *possible_keys):
        """Robustly fetch a field from a FinViz screener record.
        FinViz HTML table headers inconsistently mix full names
        ('Forward P/E') and abbreviations ('P/FCF', 'ROE'), so try
        multiple candidates and return the first non-empty match."""
        if not item:
            return ""
        for k in possible_keys:
            v = item.get(k)
            if v is not None and v != "" and str(v).lower() != "nan":
                return v
        return ""

    def get_or_create_ticker(ticker, company, sector, industry, price, change, mcap, pe, float_short, rel_vol, roe=None, debt_equity=None, item=None):
        t = ticker.upper()
        
        # Extract valuation fields if item is provided (try common name variants)
        fwd_pe = get_field(item, "Forward P/E", "Fwd P/E")
        peg = get_field(item, "PEG")
        p_fcf = get_field(item, "P/FCF", "P/Free Cash Flow")
        
        # Multi-day performance for TechScore momentum + Relative Strength (P0-1/P0-2)
        perf_week = get_field(item, "Perf Week", "Performance (Week)")
        perf_month = get_field(item, "Perf Month", "Performance (Month)")
        perf_quarter = get_field(item, "Perf Quart", "Performance (Quarter)")
        
        # Average volume for ADTV liquidity filter (P0-3)
        avg_volume = get_field(item, "Avg Volume", "Average Volume")
        
        if item:
            if not roe: roe = get_field(item, "ROE", "Return on Equity")
            if not debt_equity: debt_equity = get_field(item, "Debt/Eq", "Total Debt/Equity")

        # Compute ADTV (Average Daily Trading Value) = avg_volume × price
        adtv = ""
        try:
            av = float(avg_volume) if avg_volume else 0
            pr = float(price) if price else 0
            if av > 0 and pr > 0:
                adtv = av * pr
        except (ValueError, TypeError):
            pass

        if t not in tickers_map:
            tickers_map[t] = {
                "Ticker": t,
                "Company": company or "",
                "Sector": sector or "",
                "Industry": industry or "",
                "Price": price or "",
                "Change": change or "",
                "Market Cap": mcap or "",
                "P/E": pe or "",
                "Forward P/E": fwd_pe or "",
                "PEG": peg or "",
                "P/FCF": p_fcf or "",
                "Short Float": float_short or "",
                "Rel Volume": rel_vol or "",
                "ROE": roe or "",
                "Debt/Eq": debt_equity or "",
                "Perf Week": perf_week or "",
                "Perf Month": perf_month or "",
                "Perf Quarter": perf_quarter or "",
                "Avg Volume": avg_volume or "",
                "ADTV": adtv,
                "Score": 0,
                "TechScore": 0,
                "Reasons": [],
                "Conflicts": [],
                "Factors": {
                    "reversal": False,
                    "breakout": False,
                    "volume_spike": False,
                    "high_volatility": False,
                    "short_squeeze": False,
                    "insider_buying": False,
                    "reddit_popular": False,
                    "strong_sector": False,
                    "pullback": False,
                    "breakout_candidate": False,
                    "quality_compounder": False,
                    "analyst_upgrade": False,
                    "earnings_catalyst": False,
                    "momentum_leader": False,
                    "analyst_downgrade": False,
                    "overbought": False,
                    "bearish_momentum": False,
                    "low_liquidity": False
                }
            }
        entry = tickers_map[t]
        if not entry["Company"] and company: entry["Company"] = company
        if not entry["Sector"] and sector: entry["Sector"] = sector
        if not entry["Industry"] and industry: entry["Industry"] = industry
        if not entry["Price"] and price: entry["Price"] = price
        if not entry["Change"] and change: entry["Change"] = change
        if not entry["Market Cap"] and mcap: entry["Market Cap"] = mcap
        if not entry["P/E"] and pe: entry["P/E"] = pe
        if not entry["Forward P/E"] and fwd_pe: entry["Forward P/E"] = fwd_pe
        if not entry["PEG"] and peg: entry["PEG"] = peg
        if not entry["P/FCF"] and p_fcf: entry["P/FCF"] = p_fcf
        if not entry["Short Float"] and float_short: entry["Short Float"] = float_short
        if not entry["Rel Volume"] and rel_vol: entry["Rel Volume"] = rel_vol
        if not entry["ROE"] and roe: entry["ROE"] = roe
        if not entry["Debt/Eq"] and debt_equity: entry["Debt/Eq"] = debt_equity
        if not entry["Perf Week"] and perf_week: entry["Perf Week"] = perf_week
        if not entry["Perf Month"] and perf_month: entry["Perf Month"] = perf_month
        if not entry["Perf Quarter"] and perf_quarter: entry["Perf Quarter"] = perf_quarter
        if not entry["Avg Volume"] and avg_volume: entry["Avg Volume"] = avg_volume
        if not entry["ADTV"] and adtv: entry["ADTV"] = adtv
        return entry

    for item in oversold:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["reversal"] = True

    for item in double_bottom:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["reversal"] = True

    for item in new_high:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["breakout"] = True

    for item in triangle_ascending:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["breakout"] = True

    for item in unusual_volume:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["volume_spike"] = True

    for item in high_short_interest:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["short_squeeze"] = True

    for item in pullback:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["pullback"] = True

    for item in breakout_candidate:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["breakout_candidate"] = True

    for item in quality_compounder:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["quality_compounder"] = True

    for item in upgrades:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["analyst_upgrade"] = True

    for item in earnings_before + earnings_after:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["earnings_catalyst"] = True

    for item in most_active + top_gainers:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["momentum_leader"] = True

    for item in recent_insider_buying_signal:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["insider_buying"] = True

    for item in insiders + insiders_latest + insiders_top_week:
        ticker = item.get("Ticker")
        txn = item.get("Transaction")
        if ticker and txn and "buy" in txn.lower():
            e = get_or_create_ticker(ticker, "", "", "", "", "", "", "", "", "", None, None)
            e["Factors"]["insider_buying"] = True

    for item in reddit[:50]:
        ticker = item.get("ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("name"), "", "", "", "", "", "", "", "", None, None)
            e["Factors"]["reddit_popular"] = True

    for item in top_losers:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["bearish_momentum"] = True

    for item in wedge_up:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["breakout"] = True

    # Wedge Down is a bullish continuation pattern, classified as breakout
    for item in wedge_down:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["breakout"] = True

    for item in overbought:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["overbought"] = True

    # Most Volatile is a volatility signal, not volume; track separately
    for item in most_volatile:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["high_volatility"] = True

    for item in downgrades:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["analyst_downgrade"] = True

    top_3_sectors = []
    try:
        def parse_pct(s):
            try:
                return float(str(s).replace("%", "").strip())
            except:
                return -999.0
        sorted_sectors = sorted(sectors, key=lambda x: parse_pct(x.get("Change", 0)), reverse=True)
        top_3_sectors = [x.get("Name") for x in sorted_sectors[:3] if x.get("Name")]
    except Exception as ex:
        print("Error sorting sectors:", ex)

    # --- P0-3: Flag low-liquidity tickers (ADTV < $5M) so they can be
    # visually down-ranked or filtered on the frontend. Active traders cannot
    # realistically build positions in thin micro-caps without huge slippage. ---
    for ticker, e in tickers_map.items():
        try:
            adtv = float(e.get("ADTV") or 0)
            if adtv <= 0 or adtv < LIQUIDITY_FLOOR:
                e["Factors"]["low_liquidity"] = True
        except (ValueError, TypeError):
            e["Factors"]["low_liquidity"] = True

    # --- P0-1: Compute SPY benchmark returns for Relative Strength dimension.
    # Extract SPY daily prices from the turbulence cache's chart_series and
    # compute 5d / 20d / 63d returns. These serve as the benchmark against which
    # each stock's Perf Week/Month/Quarter is measured. ---
    spy_perf = {"5d": 0.0, "20d": 0.0, "63d": 0.0}
    try:
        turb_cache = cache.get("market_turbulence")
        if turb_cache and turb_cache.get("chart_series"):
            cs = turb_cache["chart_series"]
            spy_prices = [pt.get("spx", 0) for pt in cs if pt.get("spx", 0) > 0]
            if len(spy_prices) >= 65:
                spy_perf["5d"] = (spy_prices[-1] / spy_prices[-6] - 1) * 100
                spy_perf["20d"] = (spy_prices[-1] / spy_prices[-21] - 1) * 100
                spy_perf["63d"] = (spy_prices[-1] / spy_prices[-64] - 1) * 100
    except Exception as ex:
        print("Error computing SPY benchmark:", ex)

    res_list = []
    for ticker, e in tickers_map.items():
        reasons = []
        conflicts = []

        # 1. Technical Structure (Max 30) — P0-1: weights from scoring_config
        tech_dim = 0
        core_patterns = []
        if e["Factors"]["reversal"]:
            core_patterns.append((TECH_FACTORS["reversal"], "reason_reversal"))
        if e["Factors"]["pullback"]:
            core_patterns.append((TECH_FACTORS["pullback"], "reason_pullback"))
        if e["Factors"]["breakout"]:
            core_patterns.append((TECH_FACTORS["breakout"], "reason_breakout"))
        if e["Factors"]["breakout_candidate"]:
            core_patterns.append((TECH_FACTORS["breakout_candidate"], "reason_breakout_candidate"))

        if core_patterns:
            core_patterns.sort(key=lambda x: x[0], reverse=True)
            tech_dim += core_patterns[0][0]
            reasons.append(core_patterns[0][1])

            # Confirmation bonus for multiple aligned patterns
            if len(core_patterns) > 1:
                confirm_bonus = min((len(core_patterns) - 1) * TECH_FACTORS["confirm_bonus_per"],
                                     TECH_FACTORS["confirm_bonus_cap"])
                tech_dim += confirm_bonus
                for val, reason_key in core_patterns[1:]:
                    reasons.append(reason_key)

        if e["Factors"]["volume_spike"]:
            tech_dim += TECH_FACTORS["volume_spike"]
            reasons.append("reason_volume_spike")

        if e["Factors"]["high_volatility"]:
            tech_dim += TECH_FACTORS["high_volatility"]
            reasons.append("reason_high_volatility")

        if e["Sector"] in top_3_sectors:
            e["Factors"]["strong_sector"] = True
            tech_dim += TECH_FACTORS["strong_sector"]
            reasons.append("reason_strong_sector")

        # Signal conflict detection
        if e["Factors"]["overbought"] and (e["Factors"]["reversal"] or e["Factors"]["pullback"]):
            tech_dim += TECH_FACTORS["conflict_overbought_reversal"]
            conflicts.append("conflict_overbought_reversal")

        if e["Factors"]["overbought"] and e["Factors"]["breakout"]:
            conflicts.append("conflict_overbought_breakout")

        if e["Factors"]["reversal"] and e["Factors"]["bearish_momentum"]:
            tech_dim += TECH_FACTORS["conflict_reversal_bearish"]
            conflicts.append("conflict_reversal_bearish")

        tech_dim = max(min(tech_dim, DIMENSION_CAPS["tech"]), 0)

        # 2. Fundamentals & Corporate Insiders (Max 30) — P0-1: weights from config
        fund_dim = 0
        if e["Factors"]["insider_buying"]:
            fund_dim += FUND_FACTORS["insider_buying"]
            reasons.append("reason_insider_buying")
        if e["Factors"]["quality_compounder"]:
            fund_dim += FUND_FACTORS["quality_compounder"]
            reasons.append("reason_quality_compounder")
        if e["Factors"]["analyst_upgrade"]:
            fund_dim += FUND_FACTORS["analyst_upgrade"]
            reasons.append("reason_analyst_upgrade")
        if e["Factors"]["earnings_catalyst"]:
            fund_dim += FUND_FACTORS["earnings_catalyst"]
            reasons.append("reason_earnings_catalyst")
        if e["Factors"]["analyst_downgrade"]:
            fund_dim += FUND_FACTORS["analyst_downgrade"]
            reasons.append("reason_analyst_downgrade")

        # Quality compounder + downgrade conflict
        if e["Factors"]["quality_compounder"] and e["Factors"]["analyst_downgrade"]:
            conflicts.append("conflict_quality_downgrade")

        fund_dim = max(min(fund_dim, DIMENSION_CAPS["fund"]), 0)

        # 3. Market Sentiment & Flow (Max 15) — P0-1: weights from config
        sent_dim = 0
        if e["Factors"]["momentum_leader"]:
            sent_dim += SENT_FACTORS["momentum_leader"]
            reasons.append("reason_momentum_leader")
        if e["Factors"]["reddit_popular"]:
            sent_dim += SENT_FACTORS["reddit_popular"]
            reasons.append("reason_reddit_popular")
        if e["Factors"]["short_squeeze"]:
            if e["Factors"]["reddit_popular"] or e["Factors"]["reversal"] or e["Factors"]["breakout"] or e["Factors"]["volume_spike"]:
                sent_dim += SENT_FACTORS["short_squeeze_combined"]
                reasons.append("reason_squeeze_play")
            else:
                sent_dim += SENT_FACTORS["short_squeeze_alone"]
                reasons.append("reason_high_short_float")
        if e["Factors"]["bearish_momentum"]:
            sent_dim += SENT_FACTORS["bearish_momentum"]
            reasons.append("reason_bearish_momentum")

        sent_dim = max(min(sent_dim, DIMENSION_CAPS["sent"]), 0)

        # 4. Valuation (Max 5) — P0-1: halved from 10; minimal weight for short-term trading
        val_dim = 0
        try:
            fwd_pe_str = str(e.get("Forward P/E") or "").strip()
            peg_str = str(e.get("PEG") or "").strip()

            fwd_pe = float(fwd_pe_str) if fwd_pe_str and fwd_pe_str != "-" else 0.0
            peg = float(peg_str) if peg_str and peg_str != "-" else 0.0

            lo, hi, sc = VALUATION["fwd_pe_undervalued"]
            if lo < fwd_pe <= hi:
                val_dim += sc; reasons.append("reason_valuation_undervalued")
            else:
                lo, hi, sc = VALUATION["fwd_pe_fair"]
                if lo < fwd_pe <= hi:
                    val_dim += sc; reasons.append("reason_valuation_fair")
                else:
                    lo, hi, sc = VALUATION["fwd_pe_high_ok"]
                    if lo < fwd_pe <= hi:
                        val_dim += sc; reasons.append("reason_valuation_high_but_acceptable")

            lo, hi, sc = VALUATION["peg_undervalued"]
            if lo < peg <= hi:
                val_dim += sc; reasons.append("reason_peg_undervalued")
            else:
                lo, hi, sc = VALUATION["peg_fair"]
                if lo < peg <= hi:
                    val_dim += sc; reasons.append("reason_peg_fair")
                else:
                    lo, hi, sc = VALUATION["peg_expensive"]
                    if lo < peg <= hi:
                        val_dim += sc; reasons.append("reason_peg_expensive")
        except Exception:
            pass
        val_dim = max(min(val_dim, DIMENSION_CAPS["val"]), 0)

        # 5. Relative Strength vs SPY (Max 20) — P0-1: NEW dimension
        # Measures excess return over SPY across 5d / 20d / ~60d windows.
        # A stock outperforming the market is a true leader; one lagging is weak
        # regardless of its pattern signals. This is the active trader's edge.
        rs_dim = 0
        try:
            stock_5d = normalize_change_pct(e.get("Perf Week"))
            stock_20d = normalize_change_pct(e.get("Perf Month"))
            stock_63d = normalize_change_pct(e.get("Perf Quarter"))

            excess_5d = stock_5d - spy_perf["5d"]
            excess_20d = stock_20d - spy_perf["20d"]
            excess_63d = stock_63d - spy_perf["63d"]

            positive_count = sum(1 for x in [excess_5d, excess_20d, excess_63d] if x > 0)
            rising = excess_5d > excess_20d > excess_63d  # momentum accelerating

            if positive_count == 3 and rising:
                rs_dim = RS_SCORING["all_three_positive_and_rising"]
                reasons.append("reason_rs_leader")
            elif positive_count >= 2:
                rs_dim = RS_SCORING["two_of_three_positive"]
                reasons.append("reason_rs_strong")
            elif positive_count >= 1:
                rs_dim = RS_SCORING["one_of_three_positive"]
                reasons.append("reason_rs_neutral")
            # else: rs_dim stays 0 — stock is lagging the market
        except Exception:
            pass
        rs_dim = max(min(rs_dim, DIMENSION_CAPS["rs"]), 0)

        # Combined Score (5 dimensions)
        score = tech_dim + fund_dim + sent_dim + val_dim + rs_dim

        # TechScore: pure technical dimension scoring
        tech_score = 0
        
        # 1. Core pattern score (max 40)
        pattern_score = 0
        pattern_count = 0
        if e["Factors"]["breakout"]:
            pattern_score = max(pattern_score, 35)
            pattern_count += 1
        if e["Factors"]["breakout_candidate"]:
            pattern_score = max(pattern_score, 30)
            pattern_count += 1
        if e["Factors"]["pullback"]:
            pattern_score = max(pattern_score, 28)
            pattern_count += 1
        if e["Factors"]["reversal"]:
            pattern_score = max(pattern_score, 25)
            pattern_count += 1
        if pattern_count >= 2:
            pattern_score = min(pattern_score + 5, 40)
        tech_score += min(pattern_score, 40)
            
        # 2. Volume confirmation (max 25)
        try:
            rvol = float(e["Rel Volume"]) if e["Rel Volume"] else 0
            if rvol >= 2.0:
                tech_score += 25
            elif rvol >= 1.5:
                tech_score += 15
            elif rvol >= 1.0:
                tech_score += 10
        except:
            pass
            
        # 3. Multi-day price momentum (max 20) — P0-2
        # OLD logic used only intraday Change, which is noise for swing traders.
        # NEW logic uses 5-day (Perf Week) + 20-day (Perf Month) returns to gauge
        # real momentum. For reversal setups a controlled pullback is healthy;
        # for breakout/pullback setups positive multi-day momentum confirms strength.
        try:
            perf_5d = normalize_change_pct(e.get("Perf Week"))
            perf_20d = normalize_change_pct(e.get("Perf Month"))

            momentum_score = 0
            # 5-day momentum (max 12)
            if e["Factors"]["reversal"]:
                # Reversal: a controlled 1-10% pullback over 5 days is the ideal setup
                if -10.0 <= perf_5d <= -1.0:
                    momentum_score += 12
                elif -20.0 <= perf_5d < -10.0:
                    momentum_score += 8
                elif perf_5d > 0:
                    momentum_score += 4  # already bouncing back
            else:
                # Breakout/pullback: positive 5-day momentum confirms underlying strength
                if perf_5d > 5.0:
                    momentum_score += 12
                elif perf_5d > 2.0:
                    momentum_score += 8
                elif perf_5d > 0:
                    momentum_score += 4

            # 20-day momentum (max 8) — confirms intermediate-term trend direction
            if perf_20d > 10.0:
                momentum_score += 8
            elif perf_20d > 0:
                momentum_score += 4

            tech_score += min(momentum_score, 20)
        except:
            pass
            
        # 4. Trend environment (max 15)
        trend_bonus = 0
        if e["Sector"] in top_3_sectors:
            trend_bonus += 10
        if e["Factors"]["overbought"] and (e["Factors"]["reversal"] or e["Factors"]["pullback"]):
            trend_bonus -= 5
        tech_score += max(min(trend_bonus, 15), 0)

        e["TechScore"] = min(tech_score, 100)
        e["Score"] = score
        e["ScoreBreakdown"] = {
            "tech": tech_dim,
            "fund": fund_dim,
            "sent": sent_dim,
            "val": val_dim,
            "rs": rs_dim
        }
        e["Reasons"] = reasons
        e["Conflicts"] = conflicts

        # At least MIN_DIMENSIONS scoring dimensions required for multi-factor confluence
        dims_with_score = sum([1 for d in [tech_dim, fund_dim, sent_dim, val_dim, rs_dim] if d > 0])
        if e["Score"] >= MIN_SCORE and dims_with_score >= MIN_DIMENSIONS:
            res_list.append(e)

    res_list = sorted(res_list, key=lambda x: x["Score"], reverse=True)
    return {"data": res_list, "source": "live", "updated_at": datetime.now(timezone.utc).isoformat()}

@app.get("/api/wsb-calendar")
def get_wsb_calendar():
    cache_key = "wsb_important_events_calendar_v2"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"data": cached_data, "source": "cache", "updated_at": datetime.now(timezone.utc).isoformat()}
        
    try:
        res = requests.get("https://www.marketgrep.com/api/sentiment-report", timeout=10)
        if res.status_code != 200:
            raise HTTPException(status_code=res.status_code, detail="Failed to fetch sentiment report from marketgrep")
            
        payload = res.json()
        
        report_zh = payload.get("report_markdown", "")
        report_en = payload.get("report_markdown_en", "")
        
        def extract_table(markdown_content, title_marker):
            if not markdown_content:
                return []
            lines = markdown_content.split('\n')
            table_lines = []
            found = False
            for line in lines:
                if title_marker in line:
                    found = True
                    continue
                if found:
                    cleaned = line.strip()
                    if cleaned.startswith('|'):
                        table_lines.append(cleaned)
                    elif len(table_lines) > 0:
                        break
            if not table_lines:
                return []
            
            headers = [h.strip() for h in table_lines[0].split('|')[1:-1]]
            rows = []
            for line in table_lines[2:]:
                cols = [c.strip() for c in line.split('|')[1:-1]]
                if len(cols) >= len(headers):
                    row_dict = {}
                    for i, h in enumerate(headers):
                        row_dict[h] = cols[i]
                    rows.append(row_dict)
            return rows

        events_zh = extract_table(report_zh, "### 4.3")
        events_en = extract_table(report_en, "### 4.3")
        
        calendar_data = {
            "zh": [],
            "en": []
        }
        
        for item in events_zh:
            keys = list(item.keys())
            if len(keys) >= 3:
                calendar_data["zh"].append({
                    "date": item.get(keys[0], ""),
                    "event": item.get(keys[1], ""),
                    "focus": item.get(keys[2], "")
                })
                
        for item in events_en:
            keys = list(item.keys())
            if len(keys) >= 3:
                calendar_data["en"].append({
                    "date": item.get(keys[0], ""),
                    "event": item.get(keys[1], ""),
                    "focus": item.get(keys[2], "")
                })
        
        if not calendar_data["en"] and calendar_data["zh"]:
            calendar_data["en"] = calendar_data["zh"]
        elif not calendar_data["zh"] and calendar_data["en"]:
            calendar_data["zh"] = calendar_data["en"]
            
        cache.set(cache_key, calendar_data, expires_in=7200) # 2 hours cache
        return {"data": calendar_data, "source": "live", "updated_at": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        print(f"[ERROR] wsb-calendar: {e}")
        return {"data": {"zh": [], "en": []}, "source": "error", "error": str(e)}

@app.get("/api/turbulence")
def get_turbulence():
    cached_data = cache.get("market_turbulence")
    if cached_data:
        # Add a source indicator for debugging
        cached_data["source"] = "cache"
        return cached_data
    
    # SAFETY: When cache is empty, return a clearly-marked "no_data" state.
    # Never return NORMAL/100% — that would mislead traders into thinking the
    # market is safe and they can go full-size when we simply have no data.
    return {
        "cache_status": "no_data",
        "message": "Risk radar data not yet synced. Tap Refresh to fetch the latest market turbulence snapshot.",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": {
            "date": "",
            "state": "UNKNOWN",
            "state_color": "#9ca3af",
            "state_flags": {"normal": False, "elevated": False, "high_risk": False, "critical": False, "unknown": True},
            "position_size_pct": None,
            "turbulence": {"slow": 0.0, "fast": 0.0, "warning_threshold": 2.0, "extreme_threshold": 4.0, "cov_condition_number": 1.0, "cov_healthy": True},
            "macro_turbulence": {"slow": 0.0, "fast": 0.0, "warning_threshold": 2.0, "extreme_threshold": 4.0, "cov_condition_number": 1.0, "cov_healthy": True},
            "sector_dispersion": {"slow": 0.0, "fast": 0.0, "warning_threshold": 2.0, "extreme_threshold": 4.0, "cov_condition_number": 1.0, "cov_healthy": True},
            "spx": {"level": 0.0, "sma50": 0.0, "above_sma50": None},
            "vix": {"level": 0.0, "below_25": None, "dynamic_threshold": 25.0, "rolling_mean": 20.0, "below_dynamic": None},
            "move": {"level": 0.0, "dynamic_threshold": 80.0, "rolling_mean": 80.0, "below_dynamic": None},
            "credit": {"level": 1.35, "dynamic_threshold": 1.40, "rolling_mean": 1.35, "below_dynamic": None, "stressed": None},
            "divergence": {"active": False},
            "probit": {"probability": 0.0, "is_warning": False, "z_value": 0.0},
            "macro_plumbing": {
                "walcl": 0.0, "tga": 0.0, "rrp": 0.0, "net_liq": 0.0, "net_liq_z_score": 0.0,
                "sofr": 0.0, "iorb": 0.0, "sofr_iorb_spread": 0.0, "steepening_type": "NORMAL"
            },
            "labor": {
                "iursa": 0.0, "icsa": 0, "sos_indicator": 0.0, "sos_warning": False
            },
            "macro_contributors": [],
            "sector_contributors": []
        },
        "danger_zone_history": [],
        "chart_series": []
    }

# Serve static frontend files (works locally and packaged in Vercel)
from fastapi.staticfiles import StaticFiles
public_path = os.path.join(project_root, "public")
if os.path.exists(public_path):
    app.mount("/", StaticFiles(directory=public_path, html=True), name="static")
