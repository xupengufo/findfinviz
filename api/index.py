import os
import sys
import json
import sqlite3
import concurrent.futures
import random
from datetime import datetime, timezone
import requests
import pandas as pd
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }

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

from api.cache_manager import cache

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
        res = requests.get("https://apewisdom.io/api/v1.0/filter/all-stocks", headers=get_random_headers(), timeout=10)
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
    from api.scoring_engine import calculate_confluences
    return calculate_confluences()

@app.get("/api/wsb-calendar")
def get_wsb_calendar():
    cache_key = "wsb_important_events_calendar_v2"
    cached_data = cache.get(cache_key)
    if cached_data:
        return {"data": cached_data, "source": "cache", "updated_at": datetime.now(timezone.utc).isoformat()}
        
    try:
        res = requests.get("https://www.marketgrep.com/api/sentiment-report", headers=get_random_headers(), timeout=10)
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
