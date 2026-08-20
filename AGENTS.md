# FindFinviz

A serverless web app that surfaces US stock trading opportunities by scraping FinViz and aggregating multi-factor confluence signals.
Deployed on Vercel as a FastAPI Python function plus a modern Vite-bundled static frontend.
Data is refreshed by a scheduled GitHub Actions job that pushes scrape results into Vercel KV (Redis).

## Repository layout

- `api/index.py` - the FastAPI backend application exposing `/api/*` endpoints.
- `api/cache_manager.py` - unified caching abstraction supporting Upstash Redis REST pipeline, Redis client, and local SQLite fallback with batch `mget`.
- `api/scoring_engine.py` - the multi-factor confluence engine with batch cache queries.
- `scoring_config.py` - central configuration for scoring weights, factor thresholds, supported screener signals, and custom filters.
- `quant_models.py` - quantitative models for Mahalanobis turbulence, covariance matrix computation, and FRED macro indicators.
- `local_sync.py` - standalone sync script executed by GitHub Actions or local CLI to scrape FinViz, fetch FRED/ApeWisdom, and populate Redis/KV.
- `src/` - modular ES-module frontend source code (`main.js`, `state.js`, `confluences.js`, `turbulence/`, `styles.css`).
- `index.html` - main single-page application entry point.
- `vite.config.js` - Vite build and local development server proxy configuration.
- `finvizfinance/` - vendored clone of the `finvizfinance` scraper package.
- `backtest_radar.py` / `backtest_report.md` - standalone backtest script and generated report for the Risk Radar model.
- `cache.db` (root and `api/`) - local SQLite cache fallback.
- `.github/workflows/sync.yml` - scheduled sync job running every 4 hours.

## Tech stack

- Python 3.12+ (local venv at `.venv/` runs 3.14; CI uses 3.12).
- Backend dependencies in `requirements.txt`: fastapi, uvicorn, pandas, requests, beautifulsoup4, lxml, redis, yfinance, numpy, scipy.
- Frontend: Vanilla modern JS modules bundled with Vite.
- Charting and icons: Chart.js and Lucide icons.
- Storage: Vercel KV / Redis in production; SQLite (`cache.db`) as local/fallback cache.
- External data: FinViz (scraped via vendored `finvizfinance`), apewisdom.io (Reddit sentiment), marketgrep.com (WSB events calendar), St. Louis Fed (FRED), Yahoo Finance (via yfinance).

## Common commands

- Install Python deps: `python -m venv .venv && .venv/bin/pip install -r requirements.txt`
- Install Node deps: `npm install`
- Run the API locally: `.venv/bin/uvicorn api.index:app --reload`
- Run frontend dev server: `npm run dev` (proxies `/api` to local FastAPI)
- Build frontend: `npm run build` (outputs to `dist/`)
- Run the data sync: `npm run sync` (equivalent to `.venv/bin/python local_sync.py`)
- Backtest the Risk Radar model: `.venv/bin/python backtest_radar.py`

## Architecture and data flow

1. `local_sync.py` (run by GitHub Actions every 4 hours Mon-Sat UTC, or manually) scrapes all sources and writes cache keys such as `opps_<signal>`, `insiders_<option>`, `sectors_performance`, `industries_performance`, `reddit_sentiment`, and `market_turbulence` into Redis/KV with retries and exponential backoff.
2. `api/index.py` endpoints read from the cache first (`source: "cache"`); on a miss, some endpoints (`/api/opportunities`, `/api/insiders`, `/api/sectors`, `/api/stock/{ticker}`) scrape live and populate the cache.
3. The confluence engine in `api/scoring_engine.py` batches all signal lists in a single `cache.mget()` call, applies a 5-dimension scoring model (Technical Structure max 30, Fundamentals max 30, Market Sentiment max 15, Valuation max 5, Relative Strength max 20), records `Reasons`/`Conflicts` keys, and keeps qualifying tickers.
4. The Risk Radar model (`sync_turbulence` in `local_sync.py`) computes exponentially weighted Mahalanobis turbulence over macro and sector ETF returns, VIX/MOVE/credit complacency thresholds, and a fitted Probit crash-probability model, producing a sigmoid-mapped position size.

## Environment variables

- `REDIS_URL` / `KV_URL` / `KV_REST_API_URL` + `KV_REST_API_TOKEN` - cache backend. An `http(s)` URL selects the Upstash REST path; a `redis://` URL uses the redis client. Without any of these, everything falls back to local SQLite.
- `SYNC_API_KEY` - optional key for `/api/sync`.
- `FRED_API_KEY` - optional official St. Louis Fed FRED API key.
- `CORS_ORIGINS` - comma-separated origins, defaults to `*`.
- `.env.local` / `.env.production` are loaded manually by `local_sync.py`. Never commit real credentials.

## Deployment

- Vercel project `gallant-oppenheimer` (linked in `.vercel/project.json`).
- `vercel.json` builds `api/index.py` with `@vercel/python` and builds static assets with `@vercel/static-build` (distDir: `dist`).
- Pushing to `main` triggers both the Vercel deployment and the GitHub Actions sync workflow.
