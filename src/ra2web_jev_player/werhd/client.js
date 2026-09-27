// ra2web-jev-player 页内客户端 v1 —— 无依赖 classic script，注入后挂 window.__rj
// 职责: snapshot 全量状态 / orders 节流分批封装 / micro 150ms 微操循环 / 停摆与终局检测
// 实测约束(见 werhd/api.md §六): ≤5 单位分批、同目标 12s 节流、deploy 载具形态+45s 节流、
// 敌情用 units('enemy')、Move(0) 不还手。微操用 setTimeout 链(不用 onTick, 避开 8ms 预算)。
(() => {
  'use strict';
  const W = window.werhd;
  if (!W) { console.warn('[__rj] werhd 不存在——必须在对局进行中注入'); return; }
  if (window.__rj) { try { window.__rj.micro.stop(); } catch (e) {} }  // 重复注入: 先停旧循环

  const CFG = {
    microMs: 150,             // 微操循环间隔
    stallSeconds: 30,         // 游戏时间冻结多少真实秒判停摆
    focusRadius: 10,          // 集火搜索半径(格)
    engageRadius: 18,         // 空闲单位就近接敌半径(格)——射程外也压上去
    focusPerLoop: 16,         // 单轮最多扫描的己方单位数(控 150ms 预算)
    unitCdTicks: 18,          // per-unit 指令冷却(模拟拍, 官方同值)
    pairSeconds: 6,           // 同一"单位→目标"对的重发节流(秒)
    sameTargetSeconds: 12,    // 同一落点/目标的重发节流(秒)
    deploySeconds: 45,        // deploy 节流(秒)
    repairBelow: 0.8,         // 建筑血量低于此比例开维修
    repairMinCredits: 200,
    placeMinTicks: 20,        // 两次落位最少间隔(模拟拍)
    maintenanceEvery: 40,     // 维修/找矿/终局检查频率(微操轮数, 40*150ms=6s)
    oreRings: 10,             // 找矿螺旋半径(格)
    siteRings: 14,            // 落位螺旋半径(格)
    cameraDwellMs: 5000,      // 镜头每个景点最短停留
  };

  const st = {
    microOn: false, timer: 0, loopN: 0,
    lastGameTime: -1, stallSinceMs: 0, stallReported: false, outcome: null,
    order: new Map(),         // key -> gameSecond(同目标/落点节流)
    unitCd: new Map(),        // unitId -> tick(per-unit 冷却)
    pair: new Map(),          // "unitId:eid" -> gameSecond
    unitTarget: new Map(),    // unitId -> eid(集火记忆: 目标没变就不重发)
    repairing: new Map(),     // buildingId -> true(维修扳手已开)
    rulesCache: new Map(),    // "name:type" -> rules 副本
    lastPlace: { tick: -999, x: 0, y: 0 },
    lastFocus: null,          // {x, y, ms}
    camera: { on: true, lastMs: 0 },
    rally: null,              // Python 设置 {x,y,label}
    enemyBase: null,          // Python 设置 {x,y}
    events: [],
  };

  // ---------- 基础工具 ----------
  const nowS = () => Math.round(W.time());
  const gTick = () => W.tick() | 0;

  function ev(kind, data) {
    st.events.push(Object.assign({ kind, t: nowS() }, data || {}));
    if (st.events.length > 240) st.events.splice(0, 120);
  }
  function throttled(key, seconds) {
    const t = st.order.get(key);
    if (t !== undefined && nowS() - t < seconds) return true;
    st.order.set(key, nowS()); return false;
  }
  function unitReady(id) {
    const t = st.unitCd.get(id);
    if (t !== undefined && gTick() - t < CFG.unitCdTicks) return false;
    st.unitCd.set(id, gTick()); return true;
  }
  function chunk(ids, n) {
    const o = [];
    for (let i = 0; i < ids.length; i += n) o.push(ids.slice(i, i + n));
    return o;
  }
  function rulesOf(name, type) {
    const k = name + ':' + (type | 0);
    let r = st.rulesCache.get(k);
    if (r === undefined) {
      try { r = W.rules(name, type | 0) || null; } catch (e) { r = null; }
      st.rulesCache.set(k, r);
    }
    return r;
  }
  const dist2 = (a, b) => Math.max(Math.abs(a[0] - b[0]), Math.abs(a[1] - b[1]));  // 切比雪夫

  // ---------- orders: 节流 + ≤5 分批封装(本文件所有指令出口) ----------
  function issueOrder(ids, orderType, fn) {
    // fn(batchIds) 负责真正下发; 这里统一 per-unit 冷却
    let sent = 0;
    for (const b of chunk(ids, 5)) {
      const ok = b.filter(unitReady);
      if (!ok.length) continue;
      try { fn(ok); sent += ok.length; } catch (e) { ev('error', { m: 'order:' + String(e).slice(0, 80) }); }
    }
    return sent;
  }
  const O = {
    // 进攻行军/防守集结: 一律 AttackMove(4) —— Move(0) 在红警里"走路不还手"
    attackMove(ids, x, y) {
      if (throttled('am:' + x + ',' + y, CFG.sameTargetSeconds)) return 0;
      return issueOrder(ids, 4, (b) => W.order(b, 4, x, y));
    },
    move(ids, x, y) {
      if (throttled('mv:' + x + ',' + y, CFG.sameTargetSeconds)) return 0;
      return issueOrder(ids, 0, (b) => W.order(b, 0, x, y));
    },
    attack(ids, eid) {
      if (throttled('atk:' + eid, CFG.pairSeconds)) return 0;
      return issueOrder(ids, 2, (b) => W.order(b, 2, eid));
    },
    stop(ids) { return issueOrder(ids, 11, (b) => W.order(b, 11)); },
    gather(ids, x, y) {
      if (throttled('ga:' + x + ',' + y, 15)) return 0;
      return issueOrder(ids, 14, (b) => W.order(b, 14, x, y));
    },
    // deploy: 只认载具形态(type===7 && canDeploy), 45s 节流 —— 防车/厂横跳(实测 §六.3)
    deploy(ids) {
      if (throttled('deploy', CFG.deploySeconds)) return { sent: 0, throttled: true };
      const veh = ids.filter((id) => {
        const u = W.unit(id);
        return u && u.type === 7 && u.canDeploy;
      });
      if (!veh.length) return { sent: 0, reason: 'no-vehicle-form' };
      return { sent: issueOrder(veh, 9, (b) => W.order(b, 9)) };
    },
    produce(name, qty) { try { W.produce(name, qty || 1); return true; } catch (e) { ev('error', { m: 'produce:' + String(e).slice(0, 80) }); return false; } },
    place(name, x, y) { try { W.place(name, x, y); return true; } catch (e) { ev('error', { m: 'place:' + String(e).slice(0, 80) }); return false; } },
    repair(id) { try { W.repair(id); return true; } catch (e) { return false; } },
    sell(id) { try { W.sell(id); return true; } catch (e) { return false; } },
    cancel(name, qty) { try { W.cancel(name, qty); return true; } catch (e) { return false; } },
  };

  // ---------- 落位: canPlace 螺旋找位(锚点=建造厂, 防御建筑偏向敌方来向) ----------
  function spiralSite(name, cx, cy, towardEnemy) {
    const bias = towardEnemy && st.enemyBase
      ? Math.atan2(st.enemyBase.y - cy, st.enemyBase.x - cx) : null;
    for (let r = 2; r <= CFG.siteRings; r++) {
      let best = null, bestScore = Infinity;
      const steps = Math.min(8 + r * 4, 32);
      for (let i = 0; i < steps; i++) {
        const ang = (i / steps) * Math.PI * 2;
        const x = Math.round(cx + r * Math.cos(ang));
        const y = Math.round(cy + r * Math.sin(ang));
        let ok = false;
        try { ok = W.canPlace(name, x, y); } catch (e) { ok = false; }
        if (!ok) continue;
        let score = r;                                    // 越近越好
        if (bias !== null) {                              // 防御建筑: 越朝敌方向越好
          const d = Math.abs(Math.atan2(Math.sin(ang - bias), Math.cos(ang - bias)));
          score = d * 4 + r * 0.5;
        }
        if (score < bestScore) { bestScore = score; best = [x, y]; }
      }
      if (best) return best;
    }
    return null;
  }
  function baseAnchor() {
    const b = W.units('self').filter((u) => u.type === 2);
    for (const u of b) {
      const r = rulesOf(u.name, 2);
      if (r && r.constructionYard) return [u.tile.rx, u.tile.ry];
    }
    return b.length ? [b[0].tile.rx, b[0].tile.ry] : null;
  }

  // ---------- 找矿: 空闲矿车螺旋扫 Tiberium(LandType=9) ----------
  function findOre(cx, cy) {
    for (let r = 1; r <= CFG.oreRings; r++) {
      for (let i = 0; i < Math.min(r * 8, 24); i++) {
        const ang = (i / Math.min(r * 8, 24)) * Math.PI * 2;
        const x = Math.round(cx + r * Math.cos(ang)), y = Math.round(cy + r * Math.sin(ang));
        let t = null;
        try { t = W.map.tile(x, y); } catch (e) { t = null; }
        if (t && t.landType === 9) return [x, y];
      }
    }
    return null;
  }

  // ---------- 微操: 集火 / 矿车恢复 / 维修 / 落位 / 镜头 ----------
  function isHarvester(u) {
    if (u.type !== 7) return false;
    const r = rulesOf(u.name, 7);
    return r ? !!r.harvester : /HARV|CMIN/i.test(u.name);
  }
  function combatUnits() {
    // 可机动战斗单位: 载具/步兵/飞机, 排除矿车与基地车(基地车追敌=自杀)
    return W.units('self').filter((u) =>
      (u.type === 7 || u.type === 3 || u.type === 1)
      && !isHarvester(u) && !/^(SMCV|AMCV)$/.test(u.name));
  }
  function enemyScore(e, d) {
    let s = 30;
    if (e.type === 7) s += 30;                              // 载具威胁
    if (e.zone === 1) s += 100;                             // 空中优先(飞行兵掏家是历史死因)
    if (st.mission && st.mission.targetId === e.id) s += 80;
    s -= (e.hitPoints / (e.maxHitPoints || 1)) * 10;        // 残血优先收割
    s -= d * 3;
    return s;
  }
  function focusFire() {
    const enemies = W.units('enemy');
    if (!enemies.length) { st.unitTarget.clear(); return; }
    const mine = combatUnits();
    if (!mine.length) return;
    const round = st.loopN * CFG.focusPerLoop;              // 轮转扫描, 控单轮成本
    const slice = mine.length > CFG.focusPerLoop
      ? mine.slice(round % mine.length, (round % mine.length) + CFG.focusPerLoop)
      : mine;
    let fx = 0, fy = 0, fn = 0;
    for (const u of slice) {
      const ut = [u.tile.rx, u.tile.ry];
      let best = null, bestS = -Infinity;
      let near = null, nearD = Infinity;
      for (const e of enemies) {
        const d = dist2(ut, [e.tile.rx, e.tile.ry]);
        if (d < nearD) { nearD = d; near = e; }        // 最近敌(无论射程)
        if (d > CFG.focusRadius) continue;
        let inR = false;
        try { inR = W.inRange(u.id, e.id, 'current'); } catch (err) { inR = false; }
        if (!inR) continue;
        const s = enemyScore(e, d);
        if (s > bestS) { bestS = s; best = e; }
      }
      if (!best) {
        // 就近接敌(第26局迭代): 空闲单位向 18 格内最近敌人攻击移动——
        // 原先只在武器射程内开火, 敌人离 8-15 格时单位永远站桩(用户实测观察)
        if (u.isIdle && near && nearD <= CFG.engageRadius
            && !throttled('eng:' + u.id, 8)) {
          try { W.order([u.id], 4, near.tile.rx, near.tile.ry); } catch (e) {}
        }
        continue;
      }
      const prev = st.unitTarget.get(u.id);
      if (prev === best.id && !u.isIdle) continue;          // 已在打正确目标
      st.unitTarget.set(u.id, best.id);
      if (unitReady(u.id) && !throttled('p' + u.id + ':' + best.id, CFG.pairSeconds)) {
        try { W.order([u.id], 2, best.id); fx += ut[0]; fy += ut[1]; fn++; } catch (e) {}
      }
    }
    if (fn) st.lastFocus = { x: Math.round(fx / fn), y: Math.round(fy / fn), ms: Date.now() };
  }
  function harvestRecovery() {
    const idle = W.units('self').filter((u) => isHarvester(u) && u.isIdle);
    for (const u of idle) {
      if (throttled('ore:' + u.id, 20)) continue;
      const spot = findOre(u.tile.rx, u.tile.ry);
      if (spot) { try { W.order([u.id], 14, spot[0], spot[1]); ev('micro', { what: 'gather', id: u.id, x: spot[0], y: spot[1] }); } catch (e) {} }
    }
  }
  function maintenance() {
    // 终局/停摆判定
    if (!st.outcome) {
      let me = null;
      try { me = W.me(); } catch (e) { me = null; }
      if (me && me.defeated) setOutcome('defeat');
      else {
        const alive = W.players().filter((p) => p.combatant && !p.allied && !p.isObserver && !p.defeated);
        if (!alive.length) setOutcome('victory');
      }
    }
    if (st.outcome) return;
    // 建筑维修(<80% 且资金>200)
    let me2 = null;
    try { me2 = W.me(); } catch (e) {}
    if (me2 && me2.credits > CFG.repairMinCredits) {
      for (const b of W.units('self')) {
        if (b.type !== 2 || !b.hitPoints) continue;
        const r = (b.hitPoints / (b.maxHitPoints || 1));
        if (r < CFG.repairBelow && !st.repairing.get(b.id)) {
          if (O.repair(b.id)) { st.repairing.set(b.id, true); ev('micro', { what: 'repair', id: b.id, hp: Math.round(r * 100) }); }
        } else if (r >= 0.99 && st.repairing.get(b.id)) {
          O.repair(b.id); st.repairing.delete(b.id);        // 修满关扳手
        }
      }
    }
    // 就绪建筑落位(status===Ready(3) 占死队列, 必须落地)
    try {
      const qs = W.production.queues() || [];
      for (const q of qs) {
        if ((q.type !== 0 && q.type !== 1) || q.status !== 3) continue;
        if (gTick() - st.lastPlace.tick < CFG.placeMinTicks) continue;
        for (const item of (q.items || [])) {
          const anchor = baseAnchor();
          if (!anchor) continue;
          const site = spiralSite(item.name, anchor[0], anchor[1], q.type === 1);
          if (site && O.place(item.name, site[0], site[1])) {
            st.lastPlace = { tick: gTick(), x: site[0], y: site[1] };
            ev('place', { name: item.name, x: site[0], y: site[1] });
            break;
          }
        }
      }
    } catch (e) { ev('error', { m: 'place:' + String(e).slice(0, 80) }); }
  }
  function camera() {
    if (!st.camera.on) return;
    if (Date.now() - st.camera.lastMs < CFG.cameraDwellMs) return;
    let target = null;
    if (st.lastFocus && Date.now() - st.lastFocus.ms < 12000) target = st.lastFocus;
    else if (st.lastPlace.tick > 0 && gTick() - st.lastPlace.tick < 240) target = st.lastPlace;
    else target = st.rally || st.enemyBase;
    if (target) {
      try { W.camera.centerAt(target.x, target.y); st.camera.lastMs = Date.now(); } catch (e) {}
    }
  }
  function stallCheck() {
    const t = nowS();
    if (t === st.lastGameTime) {
      if (!st.stallSinceMs) st.stallSinceMs = Date.now();
      else if (!st.stallReported && Date.now() - st.stallSinceMs > CFG.stallSeconds * 1000) {
        ev('stall', { seconds: CFG.stallSeconds }); st.stallReported = true;
      }
    } else {
      st.lastGameTime = t; st.stallSinceMs = 0;
      if (st.stallReported) { st.stallReported = false; ev('stall', { recovered: true }); }
    }
  }
  function setOutcome(result) {
    st.outcome = { result, t: nowS() };
    ev('outcome', st.outcome);
  }

  function microBody() {
    st.loopN++;
    if (!window.werhd) { setOutcome('battle-gone'); st.microOn = false; return; }
    stallCheck();
    focusFire();
    if (st.loopN % 10 === 0) harvestRecovery();        // 轻量, 1.5s 一轮
    if (st.loopN % CFG.maintenanceEvery === 0) maintenance();
    camera();
  }
  function microLoop() {
    if (!st.microOn) return;
    try { microBody(); } catch (e) { ev('error', { m: 'micro:' + String(e).slice(0, 100) }); }
    st.timer = setTimeout(microLoop, CFG.microMs);
  }

  // ---------- snapshot / 对外 API ----------
  function unitBrief(u) {
    return { id: u.id, n: u.name, o: u.type, tl: [u.tile.rx, u.tile.ry],
             hp: u.hitPoints, mhp: u.maxHitPoints, idle: !!u.isIdle,
             dep: !!u.canDeploy, depd: !!u.isDeployed, z: u.zone };
  }
  function snapshot() {
    const w = window.werhd;
    if (!w) return { dead: true, outcome: st.outcome };
    const me = w.me();
    const queues = (w.production.queues() || []).map((q) => ({
      t: q.type, s: q.status, size: q.size, maxSize: q.maxSize,
      items: (q.items || []).map((i) => ({ n: i.name, p: Math.round((i.progress || 0) * 100),
                                          qty: i.quantity || 1, each: i.creditsEach || 0 })),
    }));
    const av = {};
    for (const t of [0, 1, 2, 3]) {
      try { av[t] = (w.production.available(t) || []).map((x) => (x && x.name) || x); }
      catch (e) { av[t] = []; }
    }
    return {
      tick: w.tick() | 0, t: Math.round(w.time()), map: w.map.size(),
      me: { credits: Math.round(me.credits), power: me.power, radarDisabled: me.radarDisabled,
            defeated: me.defeated, country: me.country || '', isObserver: me.isObserver },
      players: (w.players() || []).map((p) => ({ n: p.name, ai: !!p.isAi, def: !!p.defeated,
                                                 ally: !!p.allied, country: p.country || '' })),
      mine: w.units('self').map(unitBrief),
      enemy: w.units('enemy').map(unitBrief),
      // 含敌方建筑的目标集(打分/敌情渲染用); 与 legacy 语义一致按 @@AI 过滤平民
      hostile: w.units('hostile')
        .filter((u) => u.owner && u.owner.indexOf('@@AI') === 0)
        .map(unitBrief),
      hostileCount: w.units('hostile').length,
      queues, av,
      micro: { on: st.microOn, loopN: st.loopN, stall: st.stallReported,
               outcome: st.outcome, lastPlace: st.lastPlace },
      rally: st.rally, enemyBase: st.enemyBase,
      events: st.events.slice(-30),
    };
  }

  window.__rj = {
    version: '1.0.0',
    ping: () => 'pong',
    snapshot,
    o: O,
    micro: {
      start(opts) {
        opts = opts || {};
        if (opts.cfg) Object.assign(CFG, opts.cfg);    // 调频入口(测试/调参用)
        Object.assign(st.camera, opts.camera || {});
        if (opts.rally) st.rally = opts.rally;
        st.microOn = true;
        if (!st.timer) st.timer = setTimeout(microLoop, 0);
        ev('micro', { what: 'start' });
        return { on: true, version: window.__rj.version };
      },
      stop() { st.microOn = false; if (st.timer) { clearTimeout(st.timer); st.timer = 0; } return { on: false }; },
    },
    setRally(x, y, label) { st.rally = (x == null) ? null : { x, y, label: label || '' }; return st.rally; },
    setEnemyBase(x, y) { st.enemyBase = (x == null) ? null : { x, y }; return st.enemyBase; },
    setMission(m) { st.mission = m; return st.mission; },
    setCamera(on) { st.camera.on = !!on; return st.camera.on; },
    status: () => ({ on: st.microOn, loopN: st.loopN, outcome: st.outcome,
                     stall: st.stallReported, events: st.events.slice(-10) }),
    stop() { st.microOn = false; if (st.timer) { clearTimeout(st.timer); st.timer = 0; } return { stopped: true }; },
  };
  return 'injected';
})();
