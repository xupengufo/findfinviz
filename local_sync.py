import os
import sys
import json
import time
import requests
import pandas as pd

def retry_with_backoff(func, max_retries=3, base_delay=2):
    """Execute a function with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            print(f"  Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)

# Load environment variables from .env.local
env_file = ".env.local"
if os.path.exists(env_file):
    print(f"Loading environment from {env_file}...")
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                val = val.strip("'\"")
                os.environ[key] = val
else:
    print(f"Warning: {env_file} not found. Ensure KV_REST_API_URL and KV_REST_API_TOKEN are set in your environment.")

import redis

redis_url = os.environ.get("REDIS_URL") or os.environ.get("KV_URL") or os.environ.get("KV_REST_API_URL")
is_redis_rest = False
client = None

if redis_url:
    if redis_url.startswith("http"):
        is_redis_rest = True
        kv_url = redis_url
        kv_token = os.environ.get("KV_REST_API_TOKEN")
        headers = {"Authorization": f"Bearer {kv_token}"}
    else:
        try:
            client = redis.from_url(redis_url, decode_responses=True)
            print("Connected to Redis server.")
        except Exception as e:
            print("Failed to connect to Redis server:", e)
            sys.exit(1)
else:
    print("Error: Vercel Redis credentials missing. Please link your Vercel Redis database and run 'vercel env pull .env.local --yes' again.")
    sys.exit(1)

# Import local finvizfinance package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from finvizfinance.insider import Insider
from finvizfinance.screener.overview import Overview
from finvizfinance.group.overview import Overview as GroupOverview

def push_to_kv(key, data, expires_in=172800):  # Default 48 hours cache on KV for safety
    val_str = json.dumps(data)
    if is_redis_rest:
        url = f"{kv_url}/set/{key}?ex={expires_in}"
        try:
            res = requests.post(url, headers=headers, data=val_str, timeout=10)
            if res.status_code == 200 and res.json().get("result") == "OK":
                print(f"Successfully pushed key '{key}' to Vercel KV (REST).")
                return True
            else:
                print(f"Failed to push key '{key}' (REST):", res.status_code, res.text)
                return False
        except Exception as e:
            print(f"Error pushing key '{key}' (REST):", e)
            return False
    else:
        try:
            client.setex(key, expires_in, val_str)
            print(f"Successfully pushed key '{key}' to Vercel Redis.")
            return True
        except Exception as e:
            print(f"Error pushing key '{key}' to Redis:", e)
            return False

def sync_opportunities():
    signals = {
        "oversold": "Oversold",
        "overbought": "Overbought",
        "double_bottom": "Double Bottom",
        "wedge_up": "Wedge Up",
        "wedge_down": "Wedge Down",
        "triangle_ascending": "Triangle Ascending",
        "top_gainers": "Top Gainers",
        "new_high": "New High"
    }
    
    for key, signal_name in signals.items():
        print(f"Scraping opportunities for signal: {signal_name}...")

        def do_scrape(sig=signal_name):
            foverview = Overview()
            foverview.set_filter(signal=sig)
            return foverview.screener_view(limit=100, order="Market Cap.", ascend=False, verbose=0)

        try:
            df = retry_with_backoff(do_scrape)
            data = []
            if df is not None:
                df = df.fillna("")
                data = df.to_dict(orient="records")
            push_to_kv(f"opps_{key}", data)
            time.sleep(1.5)
        except Exception as e:
            print(f"Failed to scrape signal '{signal_name}' after retries:", e)

def sync_insiders():
    options = ["latest", "top week", "top owner trade"]
    for opt in options:
        print(f"Scraping insider trades for option: {opt}...")

        def do_scrape(option=opt):
            finsider = Insider(option=option)
            return finsider.get_insider()

        try:
            df = retry_with_backoff(do_scrape)
            data = []
            if df is not None:
                df = df.fillna("")
                data = df.to_dict(orient="records")
            key_name = f"insiders_{opt.lower().replace(' ', '_')}"
            push_to_kv(key_name, data)
            time.sleep(1.5)
        except Exception as e:
            print(f"Failed to scrape insider option '{opt}' after retries:", e)

def sync_sectors():
    print("Scraping sector performance matrix...")
    def do_scrape():
        fgoverview = GroupOverview()
        return fgoverview.screener_view(group="Sector")

    try:
        df = retry_with_backoff(do_scrape)
        data = []
        if df is not None:
            df = df.fillna("")
            data = df.to_dict(orient="records")
        push_to_kv("sectors_performance", data)
    except Exception as e:
        print("Failed to scrape sector matrix after retries:", e)

def sync_reddit():
    print("Scraping Reddit and WSB stock sentiment...")
    def do_fetch():
        res = requests.get("https://apewisdom.io/api/v1.0/filter/all-stocks", timeout=10)
        res.raise_for_status()
        return res

    try:
        res = retry_with_backoff(do_fetch)
        payload = res.json()
        data = payload.get("results", [])
        push_to_kv("reddit_sentiment", data)
    except Exception as e:
        print("Failed to sync Reddit sentiment after retries:", e)

if __name__ == "__main__":
    print("Starting local sync to Vercel KV...")
    sync_opportunities()
    sync_insiders()
    sync_sectors()
    sync_reddit()
    print("Sync completed successfully!")
