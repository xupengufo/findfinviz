import os
import json
import time
import sqlite3
import shutil
import requests
import redis

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class FallbackCache:
    def __init__(self):
        self.redis_url = os.environ.get("REDIS_URL") or os.environ.get("KV_URL") or os.environ.get("KV_REST_API_URL")
        self.is_redis = bool(self.redis_url)
        self.is_redis_rest = False
        self.client = None
        self.session = requests.Session()
        
        # Always resolve db path defensively for local fallback
        if os.environ.get("VERCEL") or not os.access(project_root, os.W_OK):
            self.db_path = "/tmp/cache.db"
            if not os.path.exists(self.db_path):
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
                    self.kv_url = self.redis_url.rstrip("/")
                    self.kv_token = os.environ.get("KV_REST_API_TOKEN")
                    if self.kv_token:
                        self.session.headers.update({"Authorization": f"Bearer {self.kv_token}"})
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
        try:
            now = int(time.time())
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM cache WHERE expires_at < ?", (now,))
                conn.commit()
        except Exception as e:
            print("Error cleaning up expired cache entries:", e)

    def get(self, key):
        if self.is_redis:
            try:
                if self.is_redis_rest:
                    res = self.session.get(f"{self.kv_url}/get/{key}", timeout=5)
                    if res.status_code == 200:
                        val = res.json().get("result")
                        if val:
                            return json.loads(val)
                else:
                    val = self.client.get(key)
                    if val:
                        return json.loads(val)
            except Exception as e:
                print(f"Redis get failed for '{key}', fallback to SQLite: {e}")
        
        try:
            now = int(time.time())
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT value, expires_at FROM cache WHERE key = ?", (key,)
                )
                row = cursor.fetchone()
                if row:
                    val_str, expires_at = row
                    # On Vercel, return stale expired cache data rather than failing
                    if os.environ.get("VERCEL") or expires_at > now:
                        return json.loads(val_str)
        except Exception as e:
            print(f"SQLite get failed for '{key}': {e}")
        return None

    def mget(self, keys: list[str]) -> dict[str, any]:
        """Fetch multiple keys in a single batch operation."""
        if not keys:
            return {}

        results = {}
        missing_keys = list(keys)

        # 1. Try Redis/Upstash REST
        if self.is_redis:
            try:
                if self.is_redis_rest:
                    pipeline_commands = [["GET", k] for k in keys]
                    res = self.session.post(
                        f"{self.kv_url}/pipeline",
                        json=pipeline_commands,
                        timeout=8
                    )
                    if res.status_code == 200:
                        payload = res.json()
                        for idx, item in enumerate(payload):
                            k = keys[idx]
                            raw_val = item.get("result")
                            if raw_val is not None:
                                try:
                                    results[k] = json.loads(raw_val)
                                    missing_keys.remove(k)
                                except Exception:
                                    pass
                else:
                    vals = self.client.mget(keys)
                    for k, val_str in zip(keys, vals):
                        if val_str is not None:
                            try:
                                results[k] = json.loads(val_str)
                                missing_keys.remove(k)
                            except Exception:
                                pass
            except Exception as e:
                print(f"Redis mget failed, fallback to SQLite: {e}")

        # 2. For any missing keys, fallback to SQLite
        if missing_keys:
            try:
                now = int(time.time())
                placeholders = ",".join("?" * len(missing_keys))
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        f"SELECT key, value, expires_at FROM cache WHERE key IN ({placeholders})",
                        missing_keys
                    )
                    rows = cursor.fetchall()
                    for k, val_str, expires_at in rows:
                        if os.environ.get("VERCEL") or expires_at > now:
                            try:
                                results[k] = json.loads(val_str)
                            except Exception:
                                pass
            except Exception as e:
                print(f"SQLite mget failed: {e}")

        return results

    def set(self, key, value, expires_in=14400):
        val_str = json.dumps(value)
        if self.is_redis:
            try:
                if self.is_redis_rest:
                    res = self.session.post(
                        f"{self.kv_url}/set/{key}?EX={expires_in}",
                        data=val_str,
                        timeout=5
                    )
                    if res.status_code == 200 and res.json().get("result") == "OK":
                        return True
                else:
                    self.client.setex(key, expires_in, val_str)
                    return True
            except Exception as e:
                print(f"Redis set failed for '{key}', fallback to SQLite: {e}")

        try:
            expires_at = int(time.time()) + expires_in
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                    (key, val_str, expires_at)
                )
                conn.commit()
            return True
        except Exception as e:
            print(f"SQLite set failed for '{key}': {e}")
            return False

cache = FallbackCache()
