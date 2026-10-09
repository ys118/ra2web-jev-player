# -*- coding: utf-8 -*-
"""Game launch state machine: fully automatic navigation from a cold browser to "skirmish in progress".

Menu flow (measured from snapshots on 2026-09-26; refs contain no menu-automation documentation at all,
so this is driven entirely by a11y snapshots):
  open https://gonghui.k0s.cn/ -> [audio-permission dialog "确定" (OK)] -> main menu "单机模式" (Single Player)
  -> "遭遇战" (Skirmish) -> setup screen (faction=Soviet, speed=2, credits=10000, AI-Easy, starting units=0)
  -> "开始游戏" (Start Game) -> poll `typeof werhd === 'object'` -> inject the in-page client.

Key invariant: after a page reload all skirmish settings reset to "Random / speed 6 / credits 10000", so
the launcher faces a fresh setup screen every time -- the player faction selector is the first
"随机（???）" (Random) entry in the snapshot.
Known pitfalls (docs/ENGINEERING-NOTES.md §3): black screen on cold load, the audio dialog reappearing on
every reload, and an injection made while the result screen is open being read as the match already ended.
"""
from __future__ import annotations

import time

from ..config import GAME_URL, MatchConfig
from ..driver.browser import Browser, BrowserError
from ..werhd.inject import WerhdClient


class LaunchError(RuntimeError):
    """The match-join flow failed."""


class GameLauncher:
    def __init__(self, browser: Browser, match: MatchConfig | None = None,
                 debug: bool = False):
        self.b = browser
        self.match = match or MatchConfig()
        self.debug = debug

    # ---------- 快照文本工具 ----------

    def _shot(self) -> str:
        return self.b.snapshot(interactive_only=True)

    def _find_ref(self, shot: str, label: str) -> str | None:
        """Return the interactive ref whose text label matches exactly."""
        for line in shot.splitlines():
            if '"%s"' % label in line and "[ref=" in line:
                return line.split("[ref=")[1].split("]")[0].strip()
        return None

    def _click_text(self, label: str, timeout: float = 20) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            ref = self._find_ref(self._shot(), label)
            if ref:
                self.b.click(ref)
                return True
            time.sleep(1.0)
        return False

    def _wait_text(self, label: str, timeout: float = 60) -> bool:
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self._find_ref(self._shot(), label):
                return True
            time.sleep(1.0)
        return False

    def _debug_shot(self, name: str) -> None:
        if self.debug:
            try:
                self.b.screenshot("launcher-%s.png" % name)
            except BrowserError:
                pass

    # ---------- 滑条（DOM 顺序：0 速度 / 1 资金 / 2 初始部队） ----------

    def _slider_values(self) -> list:
        # 注意：CLI 的 eval 本身就 JSON 编码返回值，JS 里不能再包 JSON.stringify
        # （否则拿到的是字符串，isinstance(list) 判空）——这里直接返回数组。
        v = self.b.eval(
            "Array.from(document.querySelectorAll('input[type=range]'))"
            ".map(x => Number(x.value))")
        return v if isinstance(v, list) else []

    def _wait_sliders(self, timeout: float = 15) -> list:
        """During setup-screen re-renders the sliders may briefly be absent from the DOM; wait for them."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            vals = self._slider_values()
            if len(vals) >= 3:
                return vals
            time.sleep(0.5)
        return []

    def _set_slider(self, index: int, target: int, max_presses: int = 40) -> int:
        """Set a slider value using only real arrow keys (trusted CDP events).

        Verdict from the game-51 incident: the old method "assign s.value directly + dispatch synthetic
        input/change" made the DOM read back the target value, while React/engine state never received a
        trusted event -- the calibration loop then returns without pressing a single key once delta==0.
        Through the first 50 games the speed slider never took effect; everything ran at the page default
        level 6 (the user confirmed on 2026-09-29 that games stopped at level 6).

        Current flow: focus -> ArrowLeft to the floor (the DOM value before pressing is untrustworthy,
        wash it down to the minimum first) -> ArrowRight step up to the target. Real key presses trigger
        the browser's native stepping plus trusted input events, so application state must follow. If the
        keys cannot move it and the read-back never reaches the target, the caller raises LaunchError as
        "cannot set" -- failure is preferable to fake success.
        """
        def cur():
            vals = self._slider_values()
            return vals[index] if len(vals) > index else None

        self.b.eval("document.querySelectorAll('input[type=range]')[%d].focus()" % index)
        time.sleep(0.2)
        prev = None
        for _ in range(12):                      # 压底: 量程 1-6, 12 次必到底
            v = cur()
            if v is None:
                return -1
            if prev is not None and v == prev:
                break
            prev = v
            self.b.press("ArrowLeft")
            time.sleep(0.12)
        prev = None
        for _ in range(min(max_presses, 12)):    # 步进到目标
            v = cur()
            if v is None:
                return -1
            if v == target:
                return v
            if prev is not None and v == prev:
                break                            # 推不动了(到顶或按键失效)
            prev = v
            self.b.press("ArrowRight")
            time.sleep(0.12)
        return cur()

    # ---------- 主流程 ----------

    def launch(self) -> WerhdClient:
        """Cold browser -> skirmish in progress (returns an already-injected WerhdClient).

        Forced reload: whether it currently sits at the main menu, in a match, or on the result screen, a
        refresh returns to a clean main menu (resign() pops a canvas confirmation box that is invisible to
        the DOM, so a refresh is the only reliable way to abandon a game).
        Cold loads occasionally go black / load resources slowly (measured >90s in game 27): the main-menu
        wait is a retry loop, refreshing again on a blank page.
        """
        nav = self.b.goto(GAME_URL, deadline_s=120, force=True)
        if not nav.get("ok"):
            raise LaunchError("打开游戏站失败: %s" % nav)
        # [第95局] 站点 0.87.0 音频许可弹窗: goto 后 ~10s 出现("游戏需要您的
        # 许可来播放音频…确定"), 挡住引擎启动与主选单(弹窗期 body 仅弹窗文案
        # 53 字符, 曾被误判为'站点白屏故障')。提前轮询点掉——按钮是标准
        # <button>确定, 每次点击顺带探测主选单; 出现"单机模式"即完成等待,
        # 超时也不 raise(交给下方 menu 重试循环兜底)。
        for _ in range(12):
            r = self.b.eval(
                "(function(){var t=document.body?document.body.innerText:'';"
                "var menu=t.indexOf('\\u5355\\u673a\\u6a21\\u5f0f')>=0;"
                "var b=[...document.querySelectorAll('button')]"
                ".filter(function(x){return x.innerText.trim()==='\\u786e\\u5b9a'});"
                "if(b.length){b[b.length-1].click();return 'clicked menu='+menu}"
                "return 'no-dialog menu='+menu})()")
            if isinstance(r, str) and "menu=True" in r:
                break
            time.sleep(5)
        menu_ok = False
        for attempt in range(3):
            self._dismiss_overlays()
            if self._wait_text("单机模式", timeout=60):
                menu_ok = True
                break
            self._debug_shot("menu-retry-%d" % attempt)
            # 诊断探针: 黑屏/卡加载时这里会挂或返回 -1, 结果只用于人工排查
            self.b.eval("document.body ? document.body.innerHTML.length : -1")
            self.b.goto(GAME_URL, deadline_s=120, force=True)   # 黑屏/卡加载 → 再刷
        if not menu_ok:
            raise LaunchError("主选单未出现（重试 3 轮仍失败）")
        # SPA 初始化期点击可能只 hover 不生效：点击后必须验证下一屏出现，否则重试
        for _ in range(3):
            if self._click_text("单机模式") and self._wait_text("遭遇战", timeout=15):
                break
            time.sleep(2)
        else:
            raise LaunchError("进不了'单机模式'子菜单")
        for _ in range(3):
            if self._click_text("遭遇战") and self._wait_text("开始游戏", timeout=15):
                break
            time.sleep(2)
        else:
            raise LaunchError("进不了'遭遇战'")
        self._configure_match()
        self._debug_shot("before-start")
        if not self._click_text("开始游戏"):
            raise LaunchError("找不到'开始游戏'")
        return self._wait_battle()

    def attach(self) -> WerhdClient:
        """Fallback entry when a human already started the match: only wait for the match to appear and
        inject, without touching the menus."""
        return self._wait_battle(timeout=60)

    def _dismiss_overlays(self) -> None:
        """Audio-permission dialog / previous game's result screen: click them away if present.

        [game 53] the a11y ref may land on the message-box-footer container, where click has no effect and
        the dialog never disappears -> the main menu can never appear. After the ref loop, a JS fallback
        clicks the real <button> directly (once the dialog is gone the button does not exist, a natural
        no-op).
        """
        for label in ("确定", "返回主选单"):
            for _ in range(3):
                ref = self._find_ref(self._shot(), label)
                if not ref:
                    break
                self.b.click(ref)
                time.sleep(2)
            if label == "确定":
                self.b.eval(
                    "(function(){var b=[...document.querySelectorAll('button')]"
                    ".filter(function(x){return x.innerText.trim()==='确定'});"
                    "if(b.length){b[b.length-1].click();return 'ok'}return 'none'})()")
                time.sleep(1)

    def _configure_match(self) -> None:
        m = self.match
        self._pick_faction(m.faction)
        if not self._wait_sliders():
            raise LaunchError("设置屏滑条未渲染")
        v = self._set_slider(0, m.speed)
        if v != m.speed:
            raise LaunchError("速度滑条设不到 %d（现为 %s）" % (m.speed, v))
        # [第100局] 站点 0.87.0 资金滑条上限疑似从 10000 降至 ~9100(连续两局
        # 校准停在 9100)——目标改为 min(配置, 滑条实际 max), 读不到 max 时
        # 用配置值(保留"宁可失败不可假成功"的校验)。
        _cmax = None
        try:
            _cmax = self.b.eval(
                "(function(){var s=document.querySelectorAll('input[type=range]')[1];"
                "return s?parseInt(s.max,10):null})()")
        except Exception:
            _cmax = None
        _ctarget = m.credits if not _cmax else min(m.credits, int(_cmax))
        v = None
        for _try in range(3):
            v = self._set_slider(1, _ctarget)
            if v == _ctarget:
                break
            time.sleep(2)
            self._dismiss_overlays()   # [100局] 校准失效疑因焦点被弹窗抢走
        # [100局] 0.87.0 实测定谳: DOM max=10000 但应用内把值 clamp 在 9100
        # (3 轮重试精确停 9100=稳定上限, 非焦点抖动)——接受 ≥9000 的现实
        # 上限(起步差 9% 可接受), 低于 9000 才是校准失败。
        if v is None or int(v) < 9000:
            raise LaunchError("资金滑条设不到 %d（现为 %s）" % (_ctarget, v))
        v = self._set_slider(2, 0)
        if v != 0:
            raise LaunchError("初始部队滑条设不到 0（现为 %s）" % v)
        if not self._find_ref(self._shot(), "AI-简单"):
            if not self._click_text("AI-简单", timeout=8):
                raise LaunchError("敌方难度不是 AI-简单 且选不上")

    def _pick_faction(self, faction: str) -> None:
        """Pick a faction. The setup screen is freshly reset (the player selector shows '随机（???）'):
        click the first '随机（???）' to open the dropdown -> wait for the dropdown to really render (poll for
        "美国" to appear; game 47: when headless rendering is slower than 1s, blindly re-clicking the opener
        toggles the dropdown closed) -> click the target faction -> confirm the dropdown collapsed. If the
        player is already the target faction (re-entry without a reset), clicking it to open the dropdown and
        clicking again is idempotent.
        """
        for _ in range(3):
            shot = self._shot()
            if '"美国"' in shot and '"%s"' % faction in shot:
                # 下拉已开: 点目标项
                ref = self._find_ref(shot, faction)
                self.b.click(ref)
                time.sleep(1.0)
                if '"美国"' not in self._shot():
                    return                                   # 下拉收起 = 选中
                continue
            opener = self._find_ref(shot, "随机（???）") or self._find_ref(shot, faction)
            if not opener:
                raise LaunchError("找不到阵营选择器")
            self.b.click(opener)
            # 等下拉真正渲染出来再决定是否再点（避免 toggle 关掉）
            if self._wait_text("美国", timeout=8):
                ref = self._find_ref(self._shot(), faction)
                if ref:
                    self.b.click(ref)
                    time.sleep(1.0)
                    if '"美国"' not in self._shot():
                        return
        raise LaunchError("选阵营失败: %s" % faction)

    def _wait_battle(self, timeout: float = 240) -> WerhdClient:
        t0 = time.time()
        reclicked = 0
        while time.time() - t0 < timeout:
            try:
                if self.b.eval("(typeof werhd === 'object') && !!werhd") is True:
                    client = WerhdClient(self.b)
                    client.inject()
                    return client
            except BrowserError:
                pass
            # "开始游戏"还在 = 刚才的点击没生效（加载竞态），补点
            if reclicked < 3 and self._find_ref(self._shot(), "开始游戏"):
                if self._click_text("开始游戏", timeout=5):
                    reclicked += 1
            time.sleep(3)
        raise LaunchError("等待对局超时（%ds）——加载卡住或结算屏未清" % int(timeout))
