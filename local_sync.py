import os
import sys
import json
import time
import requests
import pandas as pd

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

kv_url = os.environ.get("KV_REST_API_URL")
kv_token = os.environ.get("KV_REST_API_TOKEN")

if not kv_url or not kv_token:
    print("Error: Vercel KV credentials missing. Please link your Vercel KV database and run 'vercel env pull .env.local --yes' again.")
    sys.exit(1)

# Import local finvizfinance package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from finvizfinance.insider import Insider
from finvizfinance.screener.overview import Overview
from finvizfinance.group.overview import Overview as GroupOverview

headers = {"Authorization": f"Bearer {kv_token}"}

def push_to_kv(key, data, expires_in=172800): # Default 48 hours cache on KV for safety
    val_str = json.dumps(data)
    url = f"{kv_url}/set/{key}?ex={expires_in}"
    try:
        res = requests.post(url, headers=headers, data=val_str, timeout=10)
        if res.status_code == 200 and res.json().get("result") == "OK":
            print(f"Successfully pushed key '{key}' to Vercel KV.")
            return True
        else:
            print(f"Failed to push key '{key}':", res.status_code, res.text)
            return False
    except Exception as e:
        print(f"Error pushing key '{key}':", e)
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
        try:
            foverview = Overview()
            foverview.set_filter(signal=signal_name)
            df = foverview.screener_view(limit=25, verbose=0)
            data = []
            if df is not None:
                df = df.fillna("")
                data = df.to_dict(orient="records")
            push_to_kv(f"opps_{key}", data)
            time.sleep(1.5) # respect rate limits
        except Exception as e:
            print(f"Failed to scrape signal '{signal_name}':", e)

def sync_insiders():
    options = ["latest", "top week", "top owner trade"]
    for opt in options:
        print(f"Scraping insider trades for option: {opt}...")
        try:
            finsider = Insider(option=opt)
            df = finsider.get_insider()
            data = []
            if df is not None:
                df = df.fillna("")
                data = df.to_dict(orient="records")
            key_name = f"insiders_{opt.lower().replace(' ', '_')}"
            push_to_kv(key_name, data)
            time.sleep(1.5)
        except Exception as e:
            print(f"Failed to scrape insider option '{opt}':", e)

def sync_sectors():
    print("Scraping sector performance matrix...")
    try:
        fgoverview = GroupOverview()
        df = fgoverview.screener_view(group="Sector")
        data = []
        if df is not None:
            df = df.fillna("")
            data = df.to_dict(orient="records")
        push_to_kv("sectors_performance", data)
    except Exception as e:
        print("Failed to scrape sector matrix:", e)

if __name__ == "__main__":
    print("Starting local sync to Vercel KV...")
    sync_opportunities()
    sync_insiders()
    sync_sectors()
    print("Sync completed successfully!")
