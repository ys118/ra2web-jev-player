# -*- coding: utf-8 -*-
"""TypeSafe Jev 客户端 —— 本项目对外部模型调用的唯一封装。

端点: {base_url}/systemone, POST {"state", "questions", "model"}
题型: choice(多选一, criteria=选项→描述字典) / score(评分, criteria=有序档位数组≥2) /
      noul(概率判定, criteria 可省)
返回: answers[qid] = {"type", "choice"|"score"|"noul", "confidence", "probabilities"}
注意: noul 答案的键是 "noul" 而不是 "probability"（实测）。
密钥从环境变量 TYPESAFE_API_KEY 读取，绝不写进页面、日志或代码。
"""
from __future__ import annotations

import gzip
import json
import os
import threading
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://api.typesafe.ai/v1"
DEFAULT_MODEL = "jev-latest"
_MAX_INSTRUCTIONS = 4000
_MAX_CRITERION = 2000
_RETRYABLE_HTTP = {429, 500, 502, 503, 504, 529}


class JevError(RuntimeError):
    """调用失败（重试耗尽 / 配置错误 / 未知题型）。"""


class JevBudgetExceeded(JevError):
    """达到决策预算上限（JEV_MAX_CALLS）。"""


def _pct(sorted_latencies, q):
    if not sorted_latencies:
        return None
    i = min(int(len(sorted_latencies) * q), len(sorted_latencies) - 1)
    return round(sorted_latencies[i])


class JevClient:
    """批量语义判断客户端。一次请求问全部问题（比逐问省 ~10x 延迟与费用）。"""

    def __init__(self, api_key=None, base_url=None, model=None, max_calls=None):
        self.api_key = api_key if api_key is not None else os.environ.get("TYPESAFE_API_KEY", "")
        self.base_url = (base_url or os.environ.get("JEV_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model or os.environ.get("JEV_MODEL") or DEFAULT_MODEL
        self.max_calls = int(
            max_calls if max_calls is not None else os.environ.get("JEV_MAX_CALLS", "1500"))
        self._lock = threading.Lock()
        self._stats = {"decisions": 0, "errors": 0, "input_tokens": 0,
                       "output_tokens": 0, "latencies": []}

    # ---------- 统计 ----------

    def stats(self) -> dict:
        with self._lock:
            lat = sorted(self._stats["latencies"][-300:])
            out = {k: v for k, v in self._stats.items() if k != "latencies"}
        out.update({"p50_ms": _pct(lat, 0.50), "p95_ms": _pct(lat, 0.95), "model": self.model})
        return out

    # ---------- 请求 ----------

    @staticmethod
    def _normalize(questions: dict) -> dict:
        out = {}
        for qid, q in questions.items():
            qtype = q.get("type", "choice")
            if qtype not in ("choice", "score", "noul"):
                raise JevError("unknown question type: %r" % (qtype,))
            item = {"type": qtype,
                    "instructions": str(q.get("instructions", ""))[:_MAX_INSTRUCTIONS]}
            crit = q.get("criteria")
            if qtype == "choice":
                item["criteria"] = {str(k): str(v)[:_MAX_CRITERION] for k, v in (crit or {}).items()}
            elif qtype == "score":
                item["criteria"] = [str(c)[:_MAX_CRITERION] for c in (crit or [])]
            elif crit:
                item["criteria"] = crit
            out[str(qid)] = item
        return out

    def ask(self, state, questions: dict, timeout: float = 40) -> dict:
        """一次请求批量问全部问题；返回 answers 字典（失败抛 JevError）。"""
        if not questions:
            return {}
        with self._lock:
            if self._stats["decisions"] >= self.max_calls:
                raise JevBudgetExceeded("max calls reached: %d" % self.max_calls)
        body = json.dumps({"state": state, "questions": self._normalize(questions),
                           "model": self.model}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/systemone", data=body,
            headers={"Content-Type": "application/json", "Accept-Encoding": "identity",
                     "Authorization": "Bearer " + self.api_key})
        last = None
        for attempt in range(4):
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    raw = r.read()
                if raw[:2] == b"\x1f\x8b":          # 服务端偶发 gzip，兜底解压
                    raw = gzip.decompress(raw)
                resp = json.loads(raw.decode("utf-8"))
                self._record(time.time() - t0, resp.get("usage") or {})
                return resp.get("answers") or {}
            except urllib.error.HTTPError as e:
                last = e
                if e.code in _RETRYABLE_HTTP:
                    time.sleep(min(1.5 * (2 ** attempt), 8))
                    continue
                break
            except Exception as e:                   # 网络/解码类错误
                last = e
                time.sleep(min(1.0 * (2 ** attempt), 6))
        with self._lock:
            self._stats["errors"] += 1
        raise JevError("typesafe failed: %s" % last)

    def ask_groups(self, state, groups: dict, timeout: float = 40) -> dict:
        """官方候选组形状的便捷封装：{gid: {instructions, criteria{选项→描述}}} → 每组一道 choice。"""
        questions = {gid: {"type": "choice", "instructions": g.get("instructions", ""),
                           "criteria": g.get("criteria") or {}}
                     for gid, g in groups.items()}
        return self.ask(state, questions, timeout=timeout)

    def _record(self, seconds: float, usage: dict) -> None:
        with self._lock:
            self._stats["decisions"] += 1
            self._stats["input_tokens"] += usage.get("input_tokens") or 0
            self._stats["output_tokens"] += usage.get("output_tokens") or 0
            self._stats["latencies"].append(seconds * 1000)
