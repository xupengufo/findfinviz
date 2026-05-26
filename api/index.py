import os
import sys
import json
import sqlite3
from datetime import datetime
import requests
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Add project root to sys.path to find the cloned finvizfinance package
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from finvizfinance.quote import finvizfinance
from finvizfinance.insider import Insider
from finvizfinance.screener.overview import Overview
from finvizfinance.group.overview import Overview as GroupOverview

app = FastAPI(title="US Stock Trading Opportunities API")

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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
                    if expires_at > int(datetime.utcnow().timestamp()):
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
                expires_at = int(datetime.utcnow().timestamp()) + expires_in
                conn = sqlite3.connect(self.db_path)
                cursor = cursor = conn.cursor()
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
        "new_high": "New High"
    }

    normalized_signal = signal.lower().replace(" ", "_")
    if normalized_signal not in supported_signals:
        raise HTTPException(
            status_code=400,
            detail=f"Signal '{signal}' not supported. Choose from {list(supported_signals.keys())}"
        )

    try:
        foverview = Overview()
        # Scan S&P 500 by default to keep load light, or fetch general if no index filter
        foverview.set_filter(signal=supported_signals[normalized_signal])
        df = foverview.screener_view(limit=100, order="Market Cap.", ascend=False, verbose=0)
        
        data = []
        if df is not None:
            # Handle float conversions to make output clean
            data = df.to_dict(orient="records")
            
        cache.set(cache_key, data, expires_in=7200) # 2 hours cache for screener
        return {"data": data, "source": "live"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        raise HTTPException(status_code=500, detail=str(e))

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
        raise HTTPException(status_code=500, detail=str(e))

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
        raise HTTPException(status_code=500, detail=str(e))

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
        raise HTTPException(status_code=500, detail=str(e))

# Serve static frontend files (works locally and packaged in Vercel)
from fastapi.staticfiles import StaticFiles
public_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
if os.path.exists(public_path):
    app.mount("/", StaticFiles(directory=public_path, html=True), name="static")
