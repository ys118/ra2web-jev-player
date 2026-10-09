# -*- coding: utf-8 -*-
"""Per-game structured record GameRecord: parses unit composition / economy / stance curves
from the event stream + line log.

(Extracted verbatim from review.py: functions moved line by line, behavior unchanged; the
review conventions comments are kept at each function.)
"""
from __future__ import annotations

import re


class GameRecord:
    """Structured record of one game (parsed from the event stream + line log)."""

    def __init__(self, events: list, loglines: list):
        self.events = events
        self.loglines = loglines
        self.started_ts = next((e.get("ts") for e in events if e.get("kind") == "start"), None)
        report = next((e for e in events if e.get("kind") == "report"), None)
        self.report = report or {}
        self.outcome = self.report.get("result", "unknown")
        self.t_end = self.report.get("t")
        # 事件分类
        self.decisions = [e for e in events if e.get("kind") == "decision"]
        self.actions = [e for e in events if e.get("kind") == "action"]
        self.obs = [e for e in events if e.get("kind") == "obs"]
        self.losses = [e for e in events if e.get("kind") == "loss"]
        self.kills = [e for e in events if e.get("kind") == "kill"]
        self.places = [e for e in events if e.get("kind") == "place"]
        # 行日志分类（[第47局] 排除 "HOLD" 行——被资金闸门拒绝的意图不算建造）
        # [第53局复盘] "POWER plant (reserve)" 是电力保底路径的真实下单, 旧正则
        # 看不见 → 误报"开局缺 NAPOWR/慢 502%"。阵营由其他建造码推断
        # (NAREFN 族→NAPOWR / GAREFN 族→GAPOWR), 之后按 t 重排。
        self.build_order = [(int(m.group(1)), m.group(2)) for ln in loglines
                            if "HOLD" not in ln
                            and (m := re.search(r"t=(\d+) (?:OPENING BUILD|jev BUILD) (\w+)", ln))]
        _codes = {c for _, c in self.build_order}
        _powr = "GAPOWR" if {"GAREFN", "GAPILE", "GAWEAP"} & _codes else "NAPOWR"
        self.build_order += [(int(m.group(1)), _powr) for ln in loglines
                             if "POWER plant (reserve" in ln
                             and (m := re.search(r"t=(\d+) POWER plant", ln))]
        self.build_order.sort(key=lambda x: x[0])
        self.tanks_built = [(int(m.group(1)), m.group(2), int(m.group(3))) for ln in loglines
                            if (m := re.search(r"t=(\d+) TANK (\w+) x(\d+)", ln))]
        self.first_tank_t = self.tanks_built[0][0] if self.tanks_built else None
        self.alarms = [ln for ln in loglines if "ALARM" in ln]
        self.turtles = [ln for ln in loglines if "TURTLE" in ln]
        self.counters = [ln for ln in loglines if "-> counter" in ln]
        self.stalls = [ln for ln in loglines if "SIM STALL" in ln]
        self.stance_changes = [(m.group(1), m.group(2), m.group(3)) for ln in loglines
                               if (m := re.search(r"jev STANCE (\w+)->(\w+) \(conf ([\d.]+)\)", ln))]
        self.err_lines = [ln for ln in loglines if re.search(r"\b\w+ ERR ", ln)]
        self.enemy_base = re.search(r"ENEMY BASE spotted @\[(\d+), ?(\d+)\]", "\n".join(loglines))

    # ---------- 派生统计 ----------

    def stance_distribution(self) -> dict:
        dist = {}
        for e in self.obs:
            st = e.get("stance")
            dist[st] = dist.get(st, 0) + 1
        total = sum(dist.values()) or 1
        return {k: round(v / total, 2) for k, v in sorted(dist.items(), key=lambda kv: -kv[1])}

    def economy(self) -> dict:
        creds = [e.get("credits", 0) for e in self.obs]
        if not creds:
            return {}
        return {"avg": round(sum(creds) / len(creds)),
                "starve_frac": round(sum(1 for c in creds if c < 200) / len(creds), 2),
                "max": max(creds)}

    def army_curve(self) -> dict:
        if not self.obs:
            return {}
        # [第72局 P4] tanks_peak 口径修正: 旧"tanks"字段含 HTK 防空车
        # (71 局"坦克峰值 19"实为 HTK 计入, 误导向 starve 归因);
        # armor=重坦(HTNK-only)新口径, 旧数据无 armor 字段时回退旧值。
        armor = [e.get("armor") for e in self.obs if "armor" in e]
        out = {"my_val_peak": max(e.get("my_val", 0) for e in self.obs),
               "en_val_peak": max(e.get("en_val", 0) for e in self.obs),
               "tanks_peak": max(armor) if armor
               else max(e.get("tanks", 0) for e in self.obs)}
        if self.obs and "armor" in self.obs[-1]:
            out["death_comp"] = {k: self.obs[-1].get(k)
                                 for k in ("armor", "aav", "inf", "hostile")}
        return out

    def loss_kill(self) -> dict:
        from collections import Counter
        return {"losses": len(self.losses),
                "loss_top": Counter(e.get("n") for e in self.losses).most_common(5),
                "kills_visible": len(self.kills)}

