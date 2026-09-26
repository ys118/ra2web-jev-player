# -*- coding: utf-8 -*-
"""王二火大 Jev 本地桥接 (Python 复刻 tools/werhd-jev-server.mjs)
用途: 页面内官方 werhd-jev-player.mjs 通过本桥接调 TypeSafe jev 做决策; 同时保存事件日志.
协议:
  GET  /player.mjs           -> 官方玩家入口 (及同目录其它 *.mjs)
  POST /decide  {state, groups} -> TypeSafe 单次批量提问 -> {answers:{gid:{choice,confidence,probabilities}}, latencyMs, model}
  POST /event   {json}       -> 事件日志 (jsonl)
  GET  /status               -> 统计
  GET  /events               -> SSE 实时事件流 (看板用)
CORS 全开 (页面 https -> http://127.0.0.1 允许).
"""
import json, os, sys, time, threading, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DOCS = "D:/projects/ra2web-jev-player/refs/examples/jev"
WS = "D:/projects/ra2web-jev-player/logs"
PORT = 5174
API_KEY = os.environ.get("TYPESAFE_API_KEY", "")
BASE = os.environ.get("JEV_BASE_URL", "https://api.typesafe.ai/v1")
MODEL = os.environ.get("JEV_MODEL", "jev-latest")
LOG_PATH = os.path.join(WS, "jev-events.jsonl")
MAX_CALLS = int(os.environ.get("JEV_MAX_CALLS", "1500"))

STATS = {"decisions": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0,
         "latencies": [], "started": time.time(), "model": MODEL}
EVENTS = []          # 最近事件(内存)
EVENT_SUBS = []      # SSE 订阅者(队列)
LOCK = threading.Lock()


def log_event(ev):
    with LOCK:
        EVENTS.append(ev)
        if len(EVENTS) > 500:
            del EVENTS[:100]
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        except Exception:
            pass
        for q in list(EVENT_SUBS):
            try:
                q.append(ev)
            except Exception:
                pass


def call_typesafe(state, groups, timeout=30):
    """一次请求批量问所有 group; 返回 answers/meta"""
    questions = {}
    for gid, g in groups.items():
        crit = g.get("criteria") or {}
        if not crit:
            continue
        questions[gid] = {"type": "choice",
                          "instructions": str(g.get("instructions", ""))[:4000],
                          "criteria": {str(k): str(v)[:2000] for k, v in crit.items()}}
    if not questions:
        return {"answers": {}, "usage": {}, "model": MODEL}
    body = json.dumps({"state": state, "questions": questions, "model": MODEL},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE.rstrip("/") + "/systemone", data=body,
                                 headers={"Content-Type": "application/json",
                                          "Accept-Encoding": "identity",
                                          "Authorization": "Bearer " + API_KEY})
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if raw[:2] == bytes([31, 139]):
                    import gzip
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504, 529):
                time.sleep(min(1.5 * (2 ** attempt), 8))
                continue
            raise
        except Exception as e:
            last = e
            time.sleep(min(1.0 * (2 ** attempt), 6))
    raise RuntimeError("typesafe failed: %s" % last)


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def _read_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b"{}"

    @staticmethod
    def _dec(raw):
        for enc in ("utf-8", "gbk"):
            try:
                return raw.decode(enc)
            except Exception:
                pass
        return raw.decode("utf-8", "replace")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/status":
            with LOCK:
                s = dict(STATS)
                lat = sorted(s.pop("latencies")[-300:])
                s["p50_ms"] = round(lat[len(lat) // 2]) if lat else None
                s["p95_ms"] = round(lat[int(len(lat) * 0.95)]) if lat else None
                s["events"] = len(EVENTS)
            return self._send(200, json.dumps(s, ensure_ascii=False))
        if path == "/events":
            # SSE 实时事件流
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self._cors()
            self.send_header("Connection", "close")
            self.end_headers()
            q = []
            with LOCK:
                EVENT_SUBS.append(q)
                hist = EVENTS[-80:]
            try:
                for ev in hist:
                    self.wfile.write(("data: %s\n\n" % json.dumps(ev, ensure_ascii=False)).encode("utf-8"))
                self.wfile.flush()
                deadline = time.time() + 3600
                while time.time() < deadline:
                    if q:
                        ev = q.pop(0)
                        self.wfile.write(("data: %s\n\n" % json.dumps(ev, ensure_ascii=False)).encode("utf-8"))
                        self.wfile.flush()
                    else:
                        time.sleep(0.4)
            except Exception:
                pass
            finally:
                with LOCK:
                    if q in EVENT_SUBS:
                        EVENT_SUBS.remove(q)
            return
        if path in ("/", "/index.html"):
            try:
                with open(os.path.join(DOCS, "werhd-jev-dashboard.html"), encoding="utf-8") as f:
                    return self._send(200, f.read(), "text/html; charset=utf-8")
            except Exception as e:
                return self._send(200, "<h1>werhd jev bridge</h1><p>%s</p>" % e,
                                  "text/html; charset=utf-8")
        # 模块文件: /player.mjs 与 /werhd-jev-*.mjs 从官方 docs 目录服务
        name = os.path.basename(path)
        if name.endswith(".mjs"):
            if name == "player.mjs":
                name = "werhd-jev-player.mjs"
            fp = os.path.join(DOCS, name)
            if os.path.isfile(fp):
                with open(fp, encoding="utf-8") as f:
                    return self._send(200, f.read(), "text/javascript; charset=utf-8")
            return self._send(404, "not found: %s" % name, "text/plain")
        return self._send(404, "not found", "text/plain")

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/event":
            try:
                ev = json.loads(self._dec(self._read_body()))
            except Exception:
                ev = {"kind": "raw", "raw": True}
            log_event(ev)
            k = ev.get("kind")
            if k in ("action", "outcome", "place", "micro", "start", "stop", "stale", "error"):
                print("[%s] %s" % (time.strftime("%H:%M:%S"), json.dumps(ev, ensure_ascii=False)[:300]), flush=True)
            return self._send(200, {"ok": True})
        if path == "/decide":
            t0 = time.time()
            if STATS["decisions"] >= MAX_CALLS:
                return self._send(429, {"error": "max calls reached"})
            try:
                body = json.loads(self._dec(self._read_body()))
                state, groups = body["state"], body["groups"]
                resp = call_typesafe(state, groups)
                ans = resp.get("answers", {})
                usage = resp.get("usage", {})
                STATS["decisions"] += 1
                STATS["input_tokens"] += usage.get("input_tokens", 0) or 0
                STATS["output_tokens"] += usage.get("output_tokens", 0) or 0
                lat = (time.time() - t0) * 1000
                with LOCK:
                    STATS["latencies"].append(lat)
                out = {"answers": ans, "latencyMs": round(lat),
                       "model": resp.get("model", MODEL),
                       "usage": usage}
                print("[%s] decide #%d groups=%d %.0fms ans=%s" % (
                    time.strftime("%H:%M:%S"), STATS["decisions"], len(groups), lat,
                    {k: v.get("choice") for k, v in list(ans.items())[:4]}), flush=True)
                return self._send(200, json.dumps(out, ensure_ascii=False))
            except Exception as e:
                STATS["errors"] += 1
                print("[decide ERR] %s" % e, flush=True)
                return self._send(500, {"error": str(e)})
        return self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        pass


if __name__ == "__main__":
    if not API_KEY:
        print("WARN: TYPESAFE_API_KEY empty", flush=True)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    print("werhd jev bridge on http://127.0.0.1:%d  model=%s  docs=%s" % (PORT, MODEL, DOCS), flush=True)
    print("attach in game console: const {attachJevPlayer} = await import('http://127.0.0.1:%d/player.mjs'); window.werhdJev = await attachJevPlayer(window.werhd)" % PORT, flush=True)
    srv.serve_forever()
