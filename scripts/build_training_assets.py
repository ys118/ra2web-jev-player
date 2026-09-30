# -*- coding: utf-8 -*-
"""训练数据资产构建器：把 44 局历史对战数据整理为 dataset/ 规范结构。

输出:
  dataset/MANIFEST.jsonl          每局一条元数据（游戏号/日期/结果/数据质量层/文件指针）
  dataset/game-NNNN/meta.json     单局元数据
  dataset/game-NNNN/events.jsonl  该局事件流（有源才存）
  dataset/game-NNNN/review.md     复盘报告（有源才存）
  dataset/game-NNNN/run.log       进程 stdout 日志（文件名与局号可对上才存）
  dataset/unattributed/           无法归属到具体局号的分段（保真不丢弃）

数据分层（tier）:
  rl-trajectory  事件流完整 + 终局已知（RL 轨迹 + 回报标签）
  partial        中止局/并发污染局——事件部分可用
  legacy-meta    第 1-22 局（旧架构）仅元数据，原始行日志在 logs/bot.log
生成方式: 本脚本幂等，可重复运行（game-0045 起的新局由 game.py 实时写 run 目录）。
"""
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
OUT = ROOT / "dataset"

# 分段 → 局号 映射（2026-09-29 人工核对: 按 report 内容逐段对账）
# seg 0=官方体系(21-22混合); seg 10/11=无法归属的无报告会话(保留不丢)
SEG_MAP = {1: 23, 2: 24, 3: 25, 4: 26, 5: 27, 6: 28, 7: 29, 8: 30, 9: 31,
           12: 32, 13: 33, 14: 34, 15: 35, 16: 36, 17: 37, 18: 38, 19: 39,
           20: 40, 21: 41, 22: 42, 23: 43, 24: 44}
SEG0_NOTE = "官方体系时代（第21-22局混合, 旧格式事件）"

# 第 1-22 局元数据（旧架构, 结果出自 docs/SESSION-REPORT.md）
LEGACY = {
    1: ("defeat", "771", "全手动侦察, 基地车闲置"),
    2: ("defeat", "533", "半手动, 布完电厂无人值守"),
    3: ("defeat", "437", "部署指令重发横跳自杀"),
    4: ("defeat", "425", "jev 异常阻塞确定性 tick"),
    5: ("defeat", "833", "经济单薄被拆精炼厂"),
    6: ("defeat", "1452", "美军飞行兵掏家, 无防空"),
    7: ("defeat", "546", "大集群直推"),
    8: ("defeat", "1619", "rush 战略首验, 击杀 19"),
    9: ("defeat", "4806", "引擎过载技术冻结"),
    10: ("unknown", None, "未重启"),
    11: ("defeat", "589", "阵营盲区+模拟冻结"),
    12: ("defeat", "1288", "中盘调试空窗"),
    13: ("defeat", None, "工程夭折"),
    14: ("defeat", None, "工程夭折"),
    15: ("defeat", None, "工程夭折"),
    16: ("defeat", None, "工程夭折"),
    17: ("defeat", "1920", "快响应体系验证, 32 分钟最长"),
    18: ("defeat", "850", "阵营误判 450s 空窗"),
    19: ("defeat", "1550", "反击分批送人头, 击杀 98"),
    20: ("defeat", "1060", "防御支出吞噬坦克预算"),
    21: ("unknown", None, "官方体系首局, 渲染中断"),
    22: ("unknown", None, "官方体系, 0 失败验证"),
}

# 复盘文件 → 局号（内容已人工核对; 编号跳位见 docs/LESSONS.md）
REVIEW_MAP = {23: "0023", 24: "0024", 25: "0025", 26: "0026", 28: "0028", 29: "0029",
              33: "0030", 34: "0031", 36: "0032", 37: "0033", 38: "0034", 39: "0035",
              40: "0036", 42: "0037", 43: "0038", 44: "0039",
              45: "0040", 47: "0041", 48: "0042", 49: "0043", 50: "0044", 53: "0045", 54: "0046", 55: "0047", 56: "0048", 58: "0049", 59: "0050", 60: "0051", 61: "0052", 62: "0053", 63: "0054"}
REVIEW_DEGRADED = {29: "并发期数据, 与第 32 局事件混写"}
# [训练数据管道] 第 45 局起每局独立 run 目录（含 decisions.jsonl SFT 元组）
RUN_GAMES = {45: "run-20260929-132512", 46: "run-20260929-134527",
             47: "run-20260929-152348", 48: "run-20260929-153835",
             49: "run-20260929-214905", 50: "run-20260929-221730",
             53: "run-20260929-231736", 54: "run-20260930-134816", 55: "run-20260930-142623", 56: "run-20260930-145311",
             57: "run-20260930-152832", 58: "run-20260930-161817",
             59: "run-20260930-170418", 60: "run-20260930-171716", 61: "run-20260930-172827", 62: "run-20260930-175039", 63: "run-20260930-194316"}
# 进程 stdout 日志 → 局号（尾行 report 与局表对账）
RUNLOG_MAP = {23: "play-run.log", 24: "play24-run.log", 25: "play25-run.log",
              26: "play26-run.log", 28: "play28-run.log", 29: "play29-run.log",
              30: "play30-run.log", 31: "play31-run.log", 32: "play32-run.log",
              33: "play33-run.log", 34: "play34-run.log", 35: "play35-run.log",
              36: "play36-run.log", 37: "play37-run.log", 38: "play38-run.log",
              39: "play39-run.log", 40: "play40-run.log", 41: "play41-run.log",
              42: "play42-run.log", 43: "play43-run.log", 44: "play44-run.log"}


def split_segments():
    """按 kind==start 切分全局事件流。返回 [(idx, events)]。"""
    segs, cur = [], None
    with open(LOGS / "jev-events.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("kind") == "start":
                if cur:
                    segs.append(cur)
                cur = []
            if cur is None:
                continue
            cur.append(ev)
    if cur:
        segs.append(cur)
    return segs


def seg_meta(events):
    """从分段提取元数据。"""
    meta = {"events_count": len(events)}
    for ev in events:
        if ev.get("kind") == "report":
            meta["result"] = ev.get("result")
            meta["duration_s"] = ev.get("t")
            meta["ticks"] = ev.get("ticks")
        if ev.get("kind") == "start":
            meta["policy"] = ev.get("policy")
    kinds = {}
    for ev in events:
        kinds[ev.get("kind")] = kinds.get(ev.get("kind"), 0) + 1
    meta["event_kinds"] = kinds
    return meta


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    segs = split_segments()
    manifest = []

    # 1-22: legacy/official 元数据层
    for g in range(1, 23):
        result, dur, note = LEGACY[g]
        meta = {"game": g, "date": "2026-09-20~21" if g <= 20 else "2026-09-21",
                "era": "legacy-bot" if g <= 20 else "official-player",
                "result": result, "duration_s": dur,
                "tier": "legacy-meta", "note": note,
                "raw": "logs/bot.log (旧架构行日志, 未结构化)"}
        d = OUT / ("game-%04d" % g)
        d.mkdir(exist_ok=True)
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
        manifest.append(meta)

    # 23-44: 事件流层
    for idx, events in enumerate(segs):
        g = SEG_MAP.get(idx)
        if g is None:
            d = OUT / "unattributed"
            d.mkdir(exist_ok=True)
            (d / ("seg-%d-events.jsonl" % idx)).write_text(
                "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n",
                encoding="utf-8")
            continue
        sm = seg_meta(events)
        result = sm.get("result")
        tier = "rl-trajectory" if result else "partial"
        note = ""
        if g == 29:
            tier = "partial"
            note = REVIEW_DEGRADED[29]
        if g == 32:
            result = "victory"
            note = "结算屏被客户端重载跳过, 由进攻态势+敌全歼推断（第32局复盘）"
        d = OUT / ("game-%04d" % g)
        d.mkdir(exist_ok=True)
        meta = {"game": g, "date": "2026-09-26" if g <= 26 else ("2026-09-27" if g <= 33 else "2026-09-28"),
                "era": "self-contained", "result": result,
                "duration_s": sm.get("duration_s"), "ticks": sm.get("ticks"),
                "tier": tier, "policy": sm.get("policy"),
                "events_count": sm["events_count"],
                "event_kinds": sm["event_kinds"], "note": note}
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
        (d / "events.jsonl").write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n",
            encoding="utf-8")
        if g in REVIEW_MAP:
            src = LOGS / "games" / ("game-%s-review.md" % REVIEW_MAP[g])
            if src.exists():
                shutil.copy(src, d / "review.md")
        if g in RUNLOG_MAP:
            src = LOGS / RUNLOG_MAP[g]
            if src.exists():
                shutil.copy(src, d / "run.log")
        manifest.append(meta)

    # 45+: run 目录层（完整 SFT 元组）
    for g, run_name in RUN_GAMES.items():
        run = LOGS / "games" / run_name
        if not run.exists():
            continue
        d = OUT / ("game-%04d" % g)
        d.mkdir(exist_ok=True)
        evs = []
        for line in open(run / "events.jsonl", encoding="utf-8"):
            line = line.strip()
            if line.startswith("{"):
                evs.append(json.loads(line))
        sm = seg_meta(evs)
        n_sft = sum(1 for _ in open(run / "decisions.jsonl", encoding="utf-8")) \
            if (run / "decisions.jsonl").exists() else 0
        meta = {"game": g, "date": "2026-09-29", "era": "self-contained",
                "result": sm.get("result"), "duration_s": sm.get("duration_s"),
                "ticks": sm.get("ticks"), "tier": "sft-full" if n_sft else "partial",
                "policy": sm.get("policy"), "events_count": len(evs),
                "event_kinds": sm.get("event_kinds"), "sft_tuples": n_sft,
                "note": "完整 (state,questions,answers) SFT 元组" if n_sft else "run 无终局报告"}
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
        (d / "events.jsonl").write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in evs) + "\n",
            encoding="utf-8")
        if n_sft:
            shutil.copy(run / "decisions.jsonl", d / "decisions.jsonl")
        if (run / "report.json").exists():
            shutil.copy(run / "report.json", d / "report.json")
        if g in REVIEW_MAP:
            src = LOGS / "games" / ("game-%s-review.md" % REVIEW_MAP[g])
            if src.exists():
                shutil.copy(src, d / "review.md")
        manifest.append(meta)

    # MANIFEST
    with open(OUT / "MANIFEST.jsonl", "w", encoding="utf-8") as f:
        for m in manifest:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    # 统计
    tiers = {}
    results = {}
    for m in manifest:
        tiers[m["tier"]] = tiers.get(m["tier"], 0) + 1
        results[m["result"]] = results.get(m["result"], 0) + 1
    print("dataset 生成完毕: %d 局 | tiers=%s | results=%s" % (len(manifest), tiers, results))


if __name__ == "__main__":
    main()
