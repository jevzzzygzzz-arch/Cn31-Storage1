#!/usr/bin/env python3
# Educational Cybersecurity measures purposes: sanitized for safe sharing, review, and classroom-style inspection of the code here.

import os
import time
import threading
import argparse
from collections import deque
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard")

TOKEN_TTL = 840  # 14 minutes

_lock = threading.Lock()
_token_queue = deque()
_stats = {
    "received": 0,
    "served": 0,
    "expired": 0,
    "duplicates": 0,
    "flushed": 0,
    "start_time": time.time(),
    "peak_queue": 0,
    "last_received": None,
    "last_served": None,
    "active_workers": 0,
}

# Track active workers
_workers = set()
_worker_lock = threading.Lock()

def _purge_expired():
    now = time.time()
    removed = 0
    while _token_queue and (now - _token_queue[0]["ts"]) > TOKEN_TTL:
        _token_queue.popleft()
        removed += 1
    _stats["expired"] += removed
    return removed

def _cleanup_loop():
    while True:
        time.sleep(10)
        with _lock:
            _purge_expired()

_cleaner = threading.Thread(target=_cleanup_loop, daemon=True)
_cleaner.start()

@app.route("/api/save-token", methods=["POST"])
def receive_token():
    data = request.get_json(silent=True)
    if not data or "token" not in data:
        return jsonify({"error": "missing 'token' field"}), 400

    token = str(data["token"]).strip()
    if not token:
        return jsonify({"error": "empty token"}), 400

    # Check for duplicates
    with _lock:
        _purge_expired()
        now = time.time()
        
        # Simple duplicate check (last 100 tokens)
        duplicate = False
        for item in list(_token_queue)[-100:]:
            if item["token"] == token:
                duplicate = True
                _stats["duplicates"] += 1
                break
        
        if not duplicate:
            _token_queue.append({"token": token, "ts": now})
            _stats["received"] += 1
            _stats["last_received"] = datetime.now().isoformat()
            queue_size = len(_token_queue)
            if queue_size > _stats["peak_queue"]:
                _stats["peak_queue"] = queue_size

    return jsonify({
        "status": "ok",
        "queue_size": queue_size if not duplicate else len(_token_queue),
        "total_received": _stats["received"],
        "duplicate": duplicate,
    }), 200

@app.route("/api/get-token", methods=["GET"])
def get_token():
    with _lock:
        _purge_expired()
        if _token_queue:
            entry = _token_queue.popleft()
            _stats["served"] += 1
            _stats["last_served"] = datetime.now().isoformat()
            return jsonify({
                "token": entry["token"],
                "remaining": len(_token_queue),
                "age_seconds": round(time.time() - entry["ts"], 1),
            }), 200
        else:
            return jsonify({"error": "no tokens available", "remaining": 0}), 404

@app.route("/api/token/bulk", methods=["GET"])
def get_tokens_bulk():
    n = request.args.get("n", 1, type=int)
    n = max(1, min(n, 100))

    tokens = []
    with _lock:
        _purge_expired()
        for _ in range(n):
            if _token_queue:
                entry = _token_queue.popleft()
                tokens.append(entry["token"])
                _stats["served"] += 1
            else:
                break
        if tokens:
            _stats["last_served"] = datetime.now().isoformat()

    return jsonify({
        "tokens": tokens,
        "count": len(tokens),
        "remaining": len(_token_queue),
    }), 200

@app.route("/api/status", methods=["GET"])
def status():
    with _lock:
        _purge_expired()
        elapsed = time.time() - _stats["start_time"]
        rate = _stats["received"] / (elapsed / 60) if elapsed > 0 else 0
        
        # Calculate import rate (last minute)
        recent_tokens = []
        now = time.time()
        for item in list(_token_queue)[-10:]:
            recent_tokens.append({
                "token": item["token"][:40] + "..." if len(item["token"]) > 40 else item["token"],
                "age": round(now - item["ts"], 1)
            })

        return jsonify({
            "pool_size": len(_token_queue),
            "imported": _stats["received"],
            "served": _stats["served"],
            "expired": _stats["expired"],
            "duplicates": _stats["duplicates"],
            "flushed": _stats["flushed"],
            "peak_pool": _stats["peak_queue"],
            "import_rate": round(rate, 1),
            "uptime_seconds": round(elapsed, 1),
            "ttl_seconds": TOKEN_TTL,
            "last_received": _stats["last_received"],
            "last_served": _stats["last_served"],
            "recent_tokens": recent_tokens,
            "active_workers": len(_workers),
            "pool_percentage": round((len(_token_queue) / max(_stats["peak_queue"], 1)) * 100, 1),
        }), 200

@app.route("/api/tokens", methods=["DELETE"])
def flush_tokens():
    with _lock:
        count = len(_token_queue)
        _token_queue.clear()
        _stats["flushed"] += count
    return jsonify({"status": "flushed", "removed": count}), 200

@app.route("/api/tokens/count", methods=["GET"])
def token_count():
    with _lock:
        _purge_expired()
        return jsonify({
            "queue_size": len(_token_queue),
            "total_received": _stats["received"],
            "total_served": _stats["served"],
        }), 200

@app.route("/api/worker/register", methods=["POST"])
def register_worker():
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id", str(time.time()))
    with _worker_lock:
        _workers.add(worker_id)
        _stats["active_workers"] = len(_workers)
    return jsonify({"status": "registered", "worker_id": worker_id}), 200

@app.route("/api/worker/unregister", methods=["POST"])
def unregister_worker():
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    if worker_id:
        with _worker_lock:
            _workers.discard(worker_id)
            _stats["active_workers"] = len(_workers)
    return jsonify({"status": "unregistered"}), 200

@app.route("/", methods=["GET"])
def dashboard():
    return send_from_directory(DASHBOARD_DIR, "index.html")

@app.route("/dashboard-assets/<path:filename>", methods=["GET"])
def dashboard_assets(filename):
    return send_from_directory(DASHBOARD_DIR, filename)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "uptime": round(time.time() - _stats["start_time"], 1),
        "queue_size": len(_token_queue),
        "total_received": _stats["received"],
    })

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Token Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=5050, help="Port (default 5050)")
    parser.add_argument("--ttl", type=int, default=840, help="Token TTL in seconds (default 840 = 14min)")
    args = parser.parse_args()

    TOKEN_TTL = args.ttl

    print(f"""
[ Token Server v2.0 ]
  Mode   : RAM Only (NO STORAGE)
  Port   : {args.port}
  TTL    : {args.ttl}s ({args.ttl//60}min)
  URL    : http://{args.host}:{args.port}

  POST   /api/save-token     - Receive token
  GET    /api/get-token      - Get single token
  GET    /api/token/bulk?n=5 - Get multiple tokens
  GET    /api/status         - Dashboard stats
  DELETE /api/tokens         - Flush all tokens
  GET    /                   - Dashboard UI
""")

    app.run(host=args.host, port=args.port, debug=False, threaded=True)