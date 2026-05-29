import os
import sys
import json
import sqlite3
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

from finvizfinance.quote import finvizfinance
from finvizfinance.insider import Insider
from finvizfinance.screener.overview import Overview
from finvizfinance.screener.custom import Custom
from finvizfinance.group.overview import Overview as GroupOverview
from local_sync import run_all_sync

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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, expires_at INTEGER)"
            )
            conn.commit()
            conn.close()
            self.cleanup_expired()
        except Exception as e:
            print("Failed to initialize SQLite cache:", e)

    def cleanup_expired(self):
        if not self.is_redis:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                now = int(datetime.now(timezone.utc).timestamp())
                cursor.execute("DELETE FROM cache WHERE expires_at < ?", (now,))
                conn.commit()
                conn.close()
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
    if os.environ.get("VERCEL") and not expected_key:
        raise HTTPException(
            status_code=503,
            detail="Sync API key is not configured in environment variables."
        )
    if expected_key and api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key.")
        
    background_tasks.add_task(run_all_sync)
    return {"status": "sync_triggered", "message": "Synchronization started in the background."}

@app.get("/api/opportunities")
def get_opportunities(signal: str = "Oversold"):
    cache_key = f"opps_{signal.lower().replace(' ', '_')}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"data": cached_data, "source": "cache", "updated_at": datetime.now(timezone.utc).isoformat()}

    # Supported signals
    supported_signals = {
        "oversold": "Oversold",
        "overbought": "Overbought",
        "double_bottom": "Double Bottom",
        "wedge_up": "Wedge Up",
        "wedge_down": "Wedge Down",
        "triangle_ascending": "Triangle Ascending",
        "top_gainers": "Top Gainers",
        "top_losers": "Top Losers",
        "new_high": "New High",
        "most_active": "Most Active",
        "most_volatile": "Most Volatile",
        "unusual_volume": "Unusual Volume",
        "upgrades": "Upgrades",
        "downgrades": "Downgrades",
        "earnings_before": "Earnings Before",
        "earnings_after": "Earnings After",
        "recent_insider_buying": "Recent Insider Buying",
        "high_short_interest": "high_short_interest",
        "pullback": "pullback",
        "breakout_candidate": "breakout_candidate",
        "quality_compounder": "quality_compounder"
    }

    normalized_signal = signal.lower().replace(" ", "_")
    if normalized_signal not in supported_signals:
        raise HTTPException(
            status_code=400,
            detail=f"Signal '{signal}' not supported. Choose from {list(supported_signals.keys())}"
        )

    try:
        fcustom = Custom()
        if normalized_signal == "high_short_interest":
            fcustom.set_filter(filters_dict={"Float Short": "Over 15%"})
        elif normalized_signal == "pullback":
            fcustom.set_filter(filters_dict={
                "50-Day Simple Moving Average": "Price above SMA50",
                "200-Day Simple Moving Average": "Price above SMA200",
                "RSI (14)": "Not Overbought (<50)"
            })
        elif normalized_signal == "breakout_candidate":
            fcustom.set_filter(filters_dict={
                "52-Week High/Low": "0-5% below High",
                "Relative Volume": "Over 1.5"
            })
        elif normalized_signal == "quality_compounder":
            fcustom.set_filter(filters_dict={
                "Return on Equity": "Over +15%",
                "Debt/Equity": "Under 1",
                "P/E": "Profitable (>0)"
            })
        else:
            fcustom.set_filter(signal=supported_signals[normalized_signal])
            
        df = fcustom.screener_view(
            limit=100, 
            order="Market Cap.", 
            ascend=False, 
            verbose=0, 
            columns=[0, 1, 2, 3, 4, 6, 7, 30, 33, 38, 64, 65, 66, 67]
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
    supported_signals = [
        "oversold", "overbought", "double_bottom", "wedge_up", "wedge_down",
        "triangle_ascending", "top_gainers", "top_losers", "new_high", "most_active",
        "most_volatile", "unusual_volume", "upgrades", "downgrades", "earnings_before",
        "earnings_after", "recent_insider_buying", "high_short_interest", "pullback",
        "breakout_candidate", "quality_compounder"
    ]
    
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
        stock = finvizfinance(ticker)
        if not stock.flag:
            raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found on FinViz.")
            
        import concurrent.futures

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
            import pandas as pd
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
            import pandas as pd
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
            import pandas as pd
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

    def get_or_create_ticker(ticker, company, sector, industry, price, change, mcap, pe, float_short, rel_vol, roe=None, debt_equity=None):
        t = ticker.upper()
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
                "Short Float": float_short or "",
                "Rel Volume": rel_vol or "",
                "ROE": roe or "",
                "Debt/Eq": debt_equity or "",
                "Score": 0,
                "TechScore": 0,
                "Reasons": [],
                "Factors": {
                    "reversal": False,
                    "breakout": False,
                    "volume_spike": False,
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
                    "bearish_momentum": False
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
        if not entry["Short Float"] and float_short: entry["Short Float"] = float_short
        if not entry["Rel Volume"] and rel_vol: entry["Rel Volume"] = rel_vol
        if not entry["ROE"] and roe: entry["ROE"] = roe
        if not entry["Debt/Eq"] and debt_equity: entry["Debt/Eq"] = debt_equity
        return entry

    for item in oversold:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["reversal"] = True

    for item in double_bottom:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["reversal"] = True

    for item in new_high:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["breakout"] = True

    for item in triangle_ascending:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["breakout"] = True

    for item in unusual_volume:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["volume_spike"] = True

    for item in high_short_interest:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["short_squeeze"] = True

    for item in pullback:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["pullback"] = True

    for item in breakout_candidate:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["breakout_candidate"] = True

    for item in quality_compounder:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["quality_compounder"] = True

    for item in upgrades:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["analyst_upgrade"] = True

    for item in earnings_before + earnings_after:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["earnings_catalyst"] = True

    for item in most_active + top_gainers:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["momentum_leader"] = True

    for item in recent_insider_buying_signal:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
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
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["bearish_momentum"] = True

    for item in wedge_up:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["breakout"] = True

    for item in wedge_down:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["reversal"] = True

    for item in overbought:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["overbought"] = True

    for item in most_volatile:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
            e["Factors"]["volume_spike"] = True

    for item in downgrades:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"))
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

    res_list = []
    for ticker, e in tickers_map.items():
        reasons = []

        # 1. Technical Structure (Max 40)
        tech_dim = 0
        if e["Factors"]["reversal"]:
            tech_dim += 30
            reasons.append("Technical Reversal (超卖/底部构筑)")
        if e["Factors"]["pullback"]:
            tech_dim += 25
            reasons.append("Trend Pullback (均线趋势回调)")
        if e["Factors"]["breakout"]:
            tech_dim += 20
            reasons.append("Technical Breakout (新高/突破构筑)")
        if e["Factors"]["breakout_candidate"]:
            tech_dim += 25
            reasons.append("Breakout Candidate (放量临近历史高点)")
        
        if e["Factors"]["volume_spike"]:
            tech_dim += 10
            reasons.append("Unusual Volume (主力异动放量)")

        if e["Sector"] in top_3_sectors:
            e["Factors"]["strong_sector"] = True
            tech_dim += 5
            reasons.append("Strong Sector (处于今日强势板块)")

        # 超买与反转/回调策略矛盾时扣分
        if e["Factors"]["overbought"] and (e["Factors"]["reversal"] or e["Factors"]["pullback"]):
            tech_dim -= 10
            reasons.append("⚠️ Overbought Risk (超买与反转/回调矛盾)")

        tech_dim = max(min(tech_dim, 40), 0)

        # 2. Fundamentals & Corporate Insiders (Max 35)
        fund_dim = 0
        if e["Factors"]["insider_buying"]:
            fund_dim += 15
            reasons.append("Insider Buying (高管净买入)")
        if e["Factors"]["quality_compounder"]:
            fund_dim += 15
            reasons.append("Quality Compounder (高ROE低负债绩优)")
        if e["Factors"]["analyst_upgrade"]:
            fund_dim += 10
            reasons.append("Analyst Upgrade (分析师评级上调)")
        if e["Factors"]["earnings_catalyst"]:
            fund_dim += 5
            reasons.append("Earnings Catalyst (财报催化剂)")
        if e["Factors"]["analyst_downgrade"]:
            fund_dim -= 10
            reasons.append("⚠️ Analyst Downgrade (分析师评级下调)")

        fund_dim = max(min(fund_dim, 35), 0)

        # 3. Market Sentiment & Flow (Max 25)
        sent_dim = 0
        if e["Factors"]["momentum_leader"]:
            sent_dim += 15
            reasons.append("Market Leader (市场主力关注)")
        if e["Factors"]["reddit_popular"]:
            sent_dim += 10
            reasons.append("Reddit Popular (散户讨论活跃)")
        if e["Factors"]["short_squeeze"]:
            if e["Factors"]["reddit_popular"] or e["Factors"]["reversal"] or e["Factors"]["breakout"] or e["Factors"]["volume_spike"]:
                sent_dim += 10
                reasons.append("Squeeze Play (高卖空比且关注度高)")
            else:
                sent_dim += 5
                reasons.append("High Short Float (高卖空比例)")
        if e["Factors"]["bearish_momentum"]:
            sent_dim -= 5
            reasons.append("⚠️ Bearish Momentum (近期跌幅居前)")

        sent_dim = max(min(sent_dim, 25), 0)

        # Combined Score
        score = tech_dim + fund_dim + sent_dim

        # 计算纯技术面评分 TechScore
        tech_score = 0
        
        # 1. 核心形态得分 (最高 40) — 允许多形态叠加
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
            
        # 2. 成交量配合得分 (最高 25)
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
            
        # 3. 价格动量配合得分 (最高 20) — 反转策略适配
        try:
            change_pct = normalize_change_pct(e["Change"])
            if e["Factors"]["reversal"]:
                # 反转策略: 适度下跌是健康买入信号
                if -5.0 <= change_pct <= -1.0:
                    tech_score += 20
                elif -10.0 <= change_pct < -5.0:
                    tech_score += 15
                elif change_pct > 0:
                    tech_score += 10  # 已开始反弹
            else:
                if change_pct > 5.0:
                    tech_score += 20
                elif change_pct > 2.0:
                    tech_score += 15
                elif change_pct > 0:
                    tech_score += 10
        except:
            pass
            
        # 4. 趋势环境调整 (最高 15)
        trend_bonus = 0
        if e["Sector"] in top_3_sectors:
            trend_bonus += 10
        if e["Factors"]["overbought"] and (e["Factors"]["reversal"] or e["Factors"]["pullback"]):
            trend_bonus -= 5  # 超买与反转/回调矛盾
        elif e["Factors"]["overbought"] and e["Factors"]["breakout"]:
            trend_bonus += 5  # 超买确认突破强度
        tech_score += max(min(trend_bonus, 15), 0)

        e["TechScore"] = min(tech_score, 100)
        e["Score"] = score
        e["ScoreBreakdown"] = {
            "tech": tech_dim,
            "fund": fund_dim,
            "sent": sent_dim
        }
        e["Reasons"] = reasons

        # 至少需要 2 个维度有得分才算真正的多重共振
        dims_with_score = sum([1 for d in [tech_dim, fund_dim, sent_dim] if d > 0])
        if e["Score"] >= 40 and dims_with_score >= 2:
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

# Serve static frontend files (works locally and packaged in Vercel)
from fastapi.staticfiles import StaticFiles
public_path = os.path.join(project_root, "public")
if os.path.exists(public_path):
    app.mount("/", StaticFiles(directory=public_path, html=True), name="static")
