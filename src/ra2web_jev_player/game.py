# -*- coding: utf-8 -*-
"""Game orchestration: inject the in-page client -> macro main loop -> final battle report.

Macro tick (~1.5s): snapshot -> stall/endgame guards -> event sensing (ALARM crisis fast
response) -> §10.1 deterministic checklist -> opening build -> scouting -> the Jev five
questions (skipped during a crisis: fight first, think later) -> stance ruling -> movement
orders.
The 150ms micro loop (focus fire / ore search / repair / positioning / camera) lives in the
in-page client.js and uses zero network.

Division-of-labor principle (docs/METHODOLOGY.md): deterministic code owns mechanics, Jev only
makes the semantic calls.
"""
from __future__ import annotations

import json
import time

from .audit import Audit
from .config import MatchConfig
from .jev import JevBudgetExceeded, JevClient, JevError
from .paths import GAMES_DIR
from .strategy import planner
from .strategy.doctrine import AA_VEHICLES, HARVEST
from .strategy.questions import build_questions
from .strategy.state import combat_tanks, force_value, ucost, yard_tile
from .werhd.inject import WerhdClient


class BattleSession:
    def __init__(self, client: WerhdClient, jev: JevClient, audit: Audit,
                 match: MatchConfig | None = None):
        self.c = client
        self.jev = jev
        self.match = match or MatchConfig()
        # [训练数据] 每局独立 run 目录: decisions.jsonl(Jev 决策元组) + events.jsonl
        # (镜像) + report.json —— 后训练(SFT/RL)的数据资产, 见 AGENTS.md
        self.run_dir = GAMES_DIR / time.strftime("run-%Y%m%d-%H%M%S")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        audit.attach_mirror(self.run_dir / "events.jsonl")
        self.audit = audit
        self.mem = planner.BattleMemory()
        self.stance = "develop"
        self.tick_n = 0
        self.crisis_ticks = 0
        self._q_used = {0: False, 1: False, 2: False, 3: False}
        self.prev_mine: dict = {}     # 战斗记录: 上 tick 我方机动单位 {id: name}
        self.prev_enemy: dict = {}    # 战斗记录: 上 tick 可见敌战斗单位
        self._budget_logged = False   # 预算耗尽只报一次（第 27 局刷屏教训）
        self._q_cd = {}               # 生产指令冷却 {(队列号, 建筑名): 时刻}（第43局:
                                      #   队列号级冷却被不同名建筑轮流插队绕过）
        # 滞后一个 tick, 重发=同一建筑重复排队, 9 座精炼厂一秒排满烧掉全部现金）

    # ---------- 生命周期 ----------

    def run(self) -> dict:
        """Play a whole game to a decision. Returns the battle report dict."""
        self.c.micro_start()
        self.audit.event({"kind": "start", "policy": "ra2web-jev-player/1.0",
                          "maxDecisions": self.match.max_decisions,
                          "micro": self.c.status()})
        self.audit.log("=== ra2web-jev-player start (tick=%.1fs, max_decisions=%d) ==="
                       % (self.match.tick_interval, self.match.max_decisions))
        outcome = None
        while outcome is None:
            try:
                outcome = self._tick()
            except KeyboardInterrupt:
                self.audit.log("### interrupted by user")
                outcome = {"result": "aborted"}
            except Exception as e:
                self.audit.log("tick ERR %s" % str(e)[:200])
                time.sleep(3)
        report = self._report(outcome)
        self.audit.event({"kind": "report", **report})
        # [训练数据] 终局战报落 run 目录
        try:
            with open(self.run_dir / "report.json", "w", encoding="utf-8") as f:
                f.write(json.dumps(report, ensure_ascii=False, indent=2))
        except Exception as e:
            self.audit.log("report write ERR %s" % str(e)[:100])
        self.c.micro_stop()
        return report

    # ---------- 单 tick ----------

    def _tick(self) -> dict | None:
        self.tick_n += 1
        self._q_used = {0: False, 1: False, 2: False, 3: False}   # 本 tick 已下单的队列
        self.mem.tick_debt = 0          # [第90局] 统一生产账本: 每 tick 清零
        t0 = time.time()
        s = self.c.snapshot()
        if s.get("dead"):
            return self._page_outcome()
        if "t" not in s or "me" not in s:
            time.sleep(3)
            return None
        # 停摆守卫: 游戏秒不动 = 冻结/节流, 不发任何指令 (防指令垃圾与重复扣款)
        if self.mem.last_t == s["t"]:
            if not self.mem.stall_logged or time.time() - self.mem.stall_t > 15:
                self.audit.log("t=%s SIM STALL (time frozen) - skip actions" % s["t"])
                self.mem.stall_logged = True
                self.mem.stall_t = time.time()
            time.sleep(1.0)
            return None
        self.mem.last_t = s["t"]
        self.mem.stall_logged = False

        # 终局判定
        if s["me"]["defeated"]:
            return {"result": "defeat", "t": s["t"]}
        ais = [p for p in s["players"] if p["ai"]]
        if ais and all(p["def"] for p in ais):
            return {"result": "victory", "t": s["t"]}
        micro_outcome = (s.get("micro") or {}).get("outcome")
        if micro_outcome:
            return {"result": micro_outcome["result"], "t": s["t"]}

        # [第95局 击杀冻结检测] 94 局假僵局(enval 冻结 6600s, 90 坦克 6.4 倍
        # 战力物理上打不到卡位残部)白耗 100 分钟——冻结满 3000gs 优雅退出,
        # report result=stalled, 复盘照跑。
        try:
            frozen_s = planner.kill_freeze(self.mem, s, self.stance)
            if frozen_s >= 3000:
                self.audit.log("t=%s ZOMBIE-FREEZE %ds (enval 不动+我方碾压) - 终止僵尸局"
                               % (s["t"], frozen_s))
                return {"result": "stalled", "t": s["t"]}
            # [第101局] 我方无机动单位超时(99 局: myval=0 拖 15 分钟不判负)
            zero_s = planner.myval_zero(self.mem, s)
            if zero_s >= 300:
                self.audit.log("t=%s MYVAL-ZERO %ds (防线已亡无翻盘路径) - 终止"
                               % (s["t"], zero_s))
                return {"result": "stalled", "t": s["t"]}
        except Exception as e:
            self.audit.log("freeze ERR %s" % str(e)[:100])

        home = yard_tile(s)
        # 战斗记录: 我方损失/敌方消失差分（复盘的兵力曲线与交换比数据源;
        # 敌方消失含"失去视野"的近似, 解读时参考）
        mine_ids = {u["id"]: u["n"] for u in s["mine"] if u["o"] in (3, 7)}
        enemy_ids = {u["id"]: u["n"] for u in s["enemy"]}
        for uid, n in self.prev_mine.items():
            if uid not in mine_ids:
                self.audit.event({"kind": "loss", "t": s["t"], "n": n})
        for uid, n in self.prev_enemy.items():
            if uid not in enemy_ids:
                self.audit.event({"kind": "kill", "t": s["t"], "n": n})
                self.mem.kill_log.append((s["t"], n))
                self.mem.kill_log = self.mem.kill_log[-12:]
        self.prev_mine, self.prev_enemy = mine_ids, enemy_ids
        # 秒级战场感知: 危机速应不等 jev (先打后想, 省 ~1s)
        try:
            alarm = planner.sense_events(s, home, self.mem)
            if alarm:
                self.crisis_ticks += 1
                acts, logline = planner.crisis_response(s, home, alarm, self.mem,
                                                        stance=self.stance)
                if self.stance not in ("attack", "rush"):
                    self.stance = "defend"   # 攻势中不被 ALARM 打回防守（第30局）
                if logline:
                    self.audit.log(logline)
                self._exec(s, acts)
        except Exception as e:
            self.audit.log("sense ERR %s" % str(e)[:150])

        # §10.1 确定性清单
        try:
            self.stance, acts, logs = planner.checklist(s, home, self.stance, self.mem)
            for ln in logs:
                self.audit.log(ln)
            self._exec(s, acts)
        except Exception as e:
            self.audit.log("checklist ERR %s" % str(e)[:150])

        # 侦察与敌基地记忆
        try:
            _had_base = self.mem.enemy_base is not None
            planner.update_enemy_base(s, self.mem)
            if self.mem.enemy_base and not _had_base:
                self.audit.log("t=%s ENEMY BASE spotted @%s" % (s["t"], self.mem.enemy_base))
            if self.mem.enemy_base:
                self.c.set_enemy_base(self.mem.enemy_base[0], self.mem.enemy_base[1])
            act, logline = planner.scouting(s, home, self.mem)
            if act:
                self.audit.log(logline)
                self._exec(s, act)   # scouting 返回的就是动作列表, 勿再包一层
                                     # （[第39局] [act] 双重包装 → a 变成嵌套列表）
        except Exception as e:
            import traceback
            lines = traceback.format_exc().strip().splitlines()
            tb_src = next((ln.strip() for ln in reversed(lines)
                           if "planner" in ln or "game.py" in ln), lines[-1])
            self.audit.log("scout ERR %s | %s" % (e, tb_src[:160]))

        if self.mem.current_stance != self.stance:   # [第63局] 态势史(Jev 动态上下文)
            self.mem.stance_hist.append((s["t"], self.stance))
            self.mem.stance_hist = self.mem.stance_hist[-4:]
            self.mem.stance_since = s["t"]
        self.mem.current_stance = self.stance   # build_gate 读取（RECOVER 放开闸门）
        # 开局确定性建造序列 (不依赖 jev; 本 tick 建筑队列已被 checklist 占用时跳过,
        # 生产指令异步生效、快照滞后一 tick, 不查会双造 —— 第 24 局实测。
        # 日志只在真正执行后打 —— [第36局] 意图行被复盘当建成统计的噪音)
        try:
            act = planner.opening_build(s, self.mem)
            for ev in self.mem.open_events:      # [第67局] 自愈回退事件进日志
                self.audit.log(ev)
            self.mem.open_events = []
            if act and not self._q_used.get(0):
                if self._exec(s, [act]):
                    self.audit.log("t=%s OPENING BUILD %s" % (s["t"], act["name"]))
        except Exception as e:
            self.audit.log("opening ERR %s" % str(e)[:150])

        # Jev 语义决策——危机 tick 也问（第 27 局用户观察③: 危机时最需要 Jev 拍板;
        # 确定性危机响应早已先行, 这里 ~1s 延迟可接受）。预算耗尽降级纯确定性, 只报一次。
        try:
            ans = self._jev_ask(s, home)
            self.stance, acts, logs = planner.apply_jev(
                s, ans, self.stance, self.mem, used=dict(self._q_used))
            for ln in logs:
                self.audit.log(ln)
            self._exec(s, acts)
        except JevBudgetExceeded as e:
            if not self._budget_logged:
                self.audit.log("jev budget exhausted: %s (继续纯确定性运行)" % e)
                self._budget_logged = True
        except JevError as e:
            self.audit.log("jev ERR %s" % str(e)[:150])
        except Exception as e:
            self.audit.log("jev flow ERR %s" % str(e)[:150])

        # 确定性态势入口 + 机动指挥 (ALARM 反击令 8s 保护期内不被集结覆盖)
        try:
            self.stance, slogs = planner.stance_overrides(s, self.stance, self.mem)
            for ln in slogs:
                self.audit.log(ln)
            if time.time() - self.mem.last_defend_order < 8:
                pass  # alarm-active (hold moves)
            else:
                acts, logline = planner.movement(s, home, self.stance, self.mem)
                if acts and logline and not str(logline).endswith("(hold)"):
                    self.audit.log("t=%s MOVE %s" % (s["t"], logline))   # no-force 不刷屏
                self._exec(s, acts)
        except Exception as e:
            self.audit.log("move ERR %s" % str(e)[:150])

        if self.tick_n % 25 == 0:
            stats = self.jev.stats()
            self.audit.log("t=%s tick#%d credits=%s stance=%s | jev %d decisions p50=%sms"
                           % (s["t"], self.tick_n, s["me"]["credits"], self.stance,
                              stats["decisions"], stats["p50_ms"]))
            # 周期观测快照(复盘的经济/兵力/态势曲线数据源, ~37 游戏秒一个点)
            my_val, en_val = force_value(s)
            self.mem.val_history.append((s["t"], s["me"]["credits"], my_val, en_val))
            self.mem.val_history = self.mem.val_history[-6:]
            _mob = combat_tanks(s["mine"])
            self.audit.event({"kind": "obs", "t": s["t"],
                              "credits": s["me"]["credits"],
                              "my_val": my_val, "en_val": en_val,
                              "stance": self.stance,
                              "hostile": len(s["hostile"]),
                              "tanks": len(_mob),
                              # [第72局 P4] 兵力构成观测: armor=重坦(不含防空车),
                              # 防止"坦克峰值"把 HTK 计入导致复盘误诊(71 局教训)
                              "armor": len([u for u in _mob if u["n"] not in AA_VEHICLES]),
                              "aav": len([u for u in s["mine"] if u["n"] in AA_VEHICLES]),
                              "inf": len([u for u in s["mine"]
                                          if u["o"] not in (2, 7) and u["n"] not in HARVEST]),
                              "harv": len([u for u in s["mine"] if u["n"] in HARVEST]),
                              "power_low": bool(s["me"]["power"].get("isLowPower"))})
        time.sleep(max(0.2, self.match.tick_interval - (time.time() - t0)))
        return None

    # ---------- 执行与 Jev ----------

    def _exec(self, s: dict, acts: list) -> bool:
        """Execute an action list. Returns whether any action really ran (produce cooldown
        skips do not count -- game 36 review noise: intent logs must not be counted as
        built statistics)."""
        executed = False
        for a in acts or []:
            try:
                kind = a["act"]
                if kind == "produce":
                    q = a.get("q")
                    name = a.get("name", "")
                    # [第43局] 冷却键=队列号+建筑名: q0 级冷却会被"同队列不同名建筑
                    # 轮流插队"绕过（NAHAND 十连发烧掉全部现金, 73% 见底）;
                    # 游戏静默拒收时队列恒空, 6s 一过就重发死循环 → 建筑名级 25s
                    cd_key = (q, name) if q is not None else name
                    if time.time() - self._q_cd.get(cd_key, 0.0) < 25.0:
                        self.audit.event({"kind": "produce_skip", "q": q,
                                          "name": name})
                        continue
                    # [第90局 统一生产账本] 全局债务闸(唯一执行入口, 覆盖 checklist/
                    # opening/jev 全部下单路径): 同 tick 各决策器独立读原始现金互不
                    # 知晓 → 队列债务失控(88/89 局: 同 tick HARV+HTNK x4+NAHAND 叠
                    # 5500 债 vs 现金 ~2600, q3 僵尸订单饿死堵死 → 坦克全程绝产)。
                    # 游戏下单即锁队列, 现金不足时生产线全线暂停且已入队订单不退款。
                    # 拒单不设冷却——现金恢复后同单即可重发。
                    # [第91局 收入引擎负债豁免] 90 局实证: 债务闸把矿车/精炼厂
                    # (收入引擎)也拦死 → 矿车卡 1-2 辆收入断绝死循环(87 胜局
                    # 矿车是负债下单爬到 6 辆的)。HARV/精炼厂允许负债 ≤1200
                    # 放行(收入落地即回血); 坦克群/普通建筑维持全额拦截。
                    # [第101局 矿车重建通道(99 局教训)] ①矿车重建期(n_harv<2)
                    # HARV 全额豁免(收入即时回血>一切); ②单厂期(t>500 且
                    # n_ref==1)二厂豁免 1200→1900——99 局死环: 二厂 NAREFN
                    # 被拦 → n_ref 卡 1 → 矿车上限卡死 → 收入永不回血。
                    _cost = ucost(name) * max(1, a.get("qty", 1))
                    _eff = s["me"]["credits"] - self.mem.tick_debt
                    _invest = name in ("HARV", "NAREFN", "GAREFN")
                    if _invest:
                        _mine = s.get("mine") or []
                        _nh = len([u for u in _mine if u.get("n") in
                                   ("HARV", "CMIN") and u.get("o") != 2])
                        _nr = len([u for u in _mine if u.get("n") in
                                   ("NAREFN", "GAREFN") and u.get("o") == 2])
                        _slack = 1400 if (name in ("HARV", "CMIN") and _nh < 2) else (
                            1900 if (name in ("NAREFN", "GAREFN")
                                     and _nr == 1 and s["t"] > 500) else 1200)
                    else:
                        _slack = 0
                    if _eff < _cost and not (_invest and _eff >= _cost - _slack):
                        self.audit.log("t=%s DEBT-GATE %s x%s (debt=%d eff=%d < %d)"
                                       % (s["t"], name, a.get("qty", 1),
                                          self.mem.tick_debt, _eff, _cost))
                        continue
                    self.mem.tick_debt += _cost
                    if q is not None:
                        self._q_cd[cd_key] = time.time()
                        self._q_used[q] = True
                    if a.get("x") is not None:
                        # [第100局] 建筑指定落点(迎敌面前沿): canPlace 不行则
                        # 逐级向 home 收缩, 全部失败回退自动落点 produce。
                        try:
                            _home = yard_tile(s)
                            _bx, _by = a["x"], a["y"]
                            _placed = False
                            for _f in (1.0, 0.7, 0.45, 0.25):
                                _px = int(_home[0] + (_bx - _home[0]) * _f)
                                _py = int(_home[1] + (_by - _home[1]) * _f)
                                if self.c.can_place(name, _px, _py):
                                    self.c.place(name, _px, _py)
                                    _placed = True
                                    break
                            if not _placed:
                                self.c.produce(name, a.get("qty", 1))
                        except Exception:
                            self.c.produce(name, a.get("qty", 1))
                    else:
                        self.c.produce(name, a.get("qty", 1))
                elif kind == "attack_move":
                    self.c.attack_move(a["ids"], a["x"], a["y"])
                elif kind == "attack_obj":
                    # [第57局] 显式攻击指定目标(order type 2): 打经济不打塔
                    self.c.attack(a["ids"], a["tid"])
                elif kind == "move":
                    self.c.move(a["ids"], a["x"], a["y"])
                elif kind == "deploy":
                    ids = [u["id"] for u in s["mine"] if u["o"] == 7 and u.get("dep")]
                    if ids:
                        self.c.deploy(ids)
                        self.audit.event({"kind": "action", "what": "deploy", "ids": ids})
                self.audit.event({"kind": "action", "what": kind,
                                  "name": a.get("name"), "qty": a.get("qty"),
                                  "tid": a.get("tid")})
                executed = True
            except Exception as e:
                self.audit.log("exec ERR %s %s" % (a.get("act"), str(e)[:120]))
        return executed

    def _jev_ask(self, s: dict, home) -> dict:
        state, Q = build_questions(s, home, self.mem, self.stance)
        answers = self.jev.ask(state, Q)
        self.audit.event({"kind": "decision", "t": s["t"],
                          "answers": {k: {"choice": v.get("choice"),
                                          "confidence": v.get("confidence")}
                                      for k, v in answers.items()}})
        # [训练数据] 完整决策元组 (state, questions, answers) —— SFT 核心数据
        try:
            rec = {"kind": "sft_tuple", "t": s["t"],
                   "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                   # [2026-10-04] 决策教师溯源 clef/jev(切流生效起才有此字段;
                   # 无该字段的历史记录均为 Jev 时代, 约定见 docs/CLEF-LOCAL.md §八)
                   "teacher": self.jev.backend,
                   "stance_before": self.stance,
                   "state": state, "questions": Q, "answers": answers}
            with open(self.run_dir / "decisions.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            self.audit.log("sft write ERR %s" % str(e)[:100])
        return answers

    def _page_outcome(self) -> dict:
        """werhd already detached -> decide the outcome from the result page text.

        The result screen may show only briefly before the client auto-reloads (observed in
        game 32: after a victory it jumps straight to the loading page); poll for the text
        for 20s, and if it is not captured, rule a victory on "all enemies destroyed = we are
        still attacking".
        """
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                txt = self.c.b.eval("(document.body.innerText||'').slice(0,600)")
            except Exception:
                txt = ""
            if "胜利" in txt or "win" in txt.lower():
                return {"result": "victory", "via": "page"}
            if "失败" in txt or "defeat" in txt.lower():
                return {"result": "defeat", "via": "page"}
            time.sleep(2)
        # 结算屏没抓到: 用最后态势推断（进攻中+敌基地已知 = 我方歼敌获胜概率高）
        attacking = self.stance in ("attack", "rush")
        return {"result": "victory" if attacking else "unknown",
                "via": "inference", "stance": self.stance}

    def _report(self, outcome: dict) -> dict:
        stats = self.jev.stats()
        return {"result": outcome.get("result"), "t": outcome.get("t"),
                "ticks": self.tick_n, "crisis_ticks": self.crisis_ticks,
                "stance": self.stance,
                "jev": {k: stats[k] for k in
                        ("decisions", "errors", "input_tokens", "output_tokens",
                         "p50_ms", "p95_ms")},
                "enemy_base": self.mem.enemy_base,
                "ts": time.strftime("%Y-%m-%d %H:%M:%S")}
