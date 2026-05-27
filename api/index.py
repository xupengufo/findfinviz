import os
import sys
import json
import sqlite3
from datetime import datetime, timezone
import requests
import pandas as pd
from fastapi import FastAPI, HTTPException
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
                
        if not self.is_redis:
            self.db_path = os.path.join(project_root, "cache.db")
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, expires_at INTEGER)"
                )
                conn.commit()
                conn.close()
            except Exception as e:
                print("Failed to initialize SQLite cache:", e)

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

@app.get("/api/opportunities")
def get_opportunities(signal: str = "Oversold"):
    cache_key = f"opps_{signal.lower().replace(' ', '_')}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"data": cached_data, "source": "cache"}

    # Supported signals
    supported_signals = {
        "oversold": "Oversold",
        "overbought": "Overbought",
        "double_bottom": "Double Bottom",
        "wedge_up": "Wedge Up",
        "wedge_down": "Wedge Down",
        "triangle_ascending": "Triangle Ascending",
        "top_gainers": "Top Gainers",
        "new_high": "New High",
        "unusual_volume": "Unusual Volume",
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
        return {"data": data, "source": "live"}
    except Exception as e:
        print(f"[ERROR] opportunities: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch opportunities data.")

@app.get("/api/insiders")
def get_insiders(option: str = "top owner trade"):
    cache_key = f"insiders_{option.lower().replace(' ', '_')}"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"data": cached_data, "source": "cache"}

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
        return {"data": data, "source": "live"}
    except Exception as e:
        print(f"[ERROR] insiders: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch insider data.")

@app.get("/api/sectors")
def get_sectors():
    cache_key = "sectors_performance"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"data": cached_data, "source": "cache"}

    try:
        fgoverview = GroupOverview()
        df = fgoverview.screener_view(group="Sector")
        
        data = []
        if df is not None:
            df = df.fillna("")
            data = df.to_dict(orient="records")
            
        cache.set(cache_key, data, expires_in=14400) # 4 hours cache
        return {"data": data, "source": "live"}
    except Exception as e:
        print(f"[ERROR] sectors: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch sector data.")

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
            
        info = stock.ticker_full_info()
        
        res_info = {
            "fundament": info.get("fundament", {}),
            "description": stock.ticker_description(),
            "peers": stock.ticker_peer(),
            "etfs": stock.ticker_etf_holders(),
        }
        
        if info.get("ratings_outer") is not None:
            df_ratings = info["ratings_outer"].copy().fillna("")
            if "Date" in df_ratings.columns:
                df_ratings["Date"] = df_ratings["Date"].apply(lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x))
            res_info["ratings_outer"] = df_ratings.to_dict(orient="records")
        else:
            res_info["ratings_outer"] = []
            
        if info.get("news") is not None:
            df_news = info["news"].copy().fillna("")
            if "Date" in df_news.columns:
                df_news["Date"] = df_news["Date"].apply(lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x))
            res_info["news"] = df_news.to_dict(orient="records")
        else:
            res_info["news"] = []
            
        if info.get("inside trader") is not None:
            df_insider = info["inside trader"].copy().fillna("")
            res_info["inside_trader"] = df_insider.to_dict(orient="records")
        else:
            res_info["inside_trader"] = []
            
        cache.set(cache_key, res_info, expires_in=14400) # 4 hours cache for single stock data
        return {"data": res_info, "source": "live"}
    except Exception as e:
        print(f"[ERROR] stock {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch stock details.")

@app.get("/api/confluences")
def get_confluences():
    cache_key = "confluences_all"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"data": cached_data, "source": "cache"}

    oversold = cache.get("opps_oversold") or []
    double_bottom = cache.get("opps_double_bottom") or []
    new_high = cache.get("opps_new_high") or []
    triangle_ascending = cache.get("opps_triangle_ascending") or []
    unusual_volume = cache.get("opps_unusual_volume") or []
    high_short_interest = cache.get("opps_high_short_interest") or []
    pullback = cache.get("opps_pullback") or []
    breakout_candidate = cache.get("opps_breakout_candidate") or []
    quality_compounder = cache.get("opps_quality_compounder") or []
    
    insiders = cache.get("insiders_top_owner_trade") or []
    insiders_latest = cache.get("insiders_latest") or []
    insiders_top_week = cache.get("insiders_top_week") or []
    
    reddit = cache.get("reddit_sentiment") or []
    sectors = cache.get("sectors_performance") or []

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
                    "quality_compounder": False
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
        score = 0
        reasons = []

        if e["Factors"]["reversal"]:
            score += 30
            reasons.append("Technical Reversal (超卖/底部构筑)")
        elif e["Factors"]["breakout"]:
            score += 20
            reasons.append("Technical Breakout (新高/突破构筑)")
        
        if e["Factors"]["volume_spike"]:
            score += 15
            reasons.append("Unusual Volume (主力异动放量)")

        if e["Factors"]["insider_buying"]:
            score += 30
            reasons.append("Insider Buying (高管净买入)")

        if e["Factors"]["reddit_popular"]:
            score += 20
            reasons.append("Reddit Popular (散户讨论活跃)")

        if e["Sector"] in top_3_sectors:
            e["Factors"]["strong_sector"] = True
            score += 20
            reasons.append("Strong Sector (处于今日强势板块)")

        if e["Factors"]["short_squeeze"]:
            if e["Factors"]["reddit_popular"] or e["Factors"]["reversal"] or e["Factors"]["breakout"] or e["Factors"]["volume_spike"]:
                score += 15
                reasons.append("Squeeze Play (高卖空比且关注度高)")
            else:
                score += 10
                reasons.append("High Short Float (高卖空比例)")

        if e["Factors"]["pullback"]:
            score += 25
            reasons.append("Trend Pullback (均线趋势回调)")

        if e["Factors"]["breakout_candidate"]:
            score += 25
            reasons.append("Breakout Candidate (放量临近历史高点)")

        if e["Factors"]["quality_compounder"]:
            score += 20
            reasons.append("Quality Compounder (高ROE低负债绩优)")

        e["Score"] = min(score, 100)
        e["Reasons"] = reasons

        if e["Score"] >= 40 and (e["Factors"]["reversal"] or e["Factors"]["breakout"] or e["Factors"]["volume_spike"] or e["Factors"]["insider_buying"] or e["Factors"]["pullback"] or e["Factors"]["breakout_candidate"] or e["Factors"]["quality_compounder"]):
            res_list.append(e)

    res_list = sorted(res_list, key=lambda x: x["Score"], reverse=True)
    cache.set(cache_key, res_list, expires_in=7200) # 2 hours cache
    return {"data": res_list, "source": "live"}

# Serve static frontend files (works locally and packaged in Vercel)
from fastapi.staticfiles import StaticFiles
public_path = os.path.join(project_root, "public")
if os.path.exists(public_path):
    app.mount("/", StaticFiles(directory=public_path, html=True), name="static")
