// Ordinary player-side strategy; no engine objects, private map data, or unit-name tables.
const dist = (a, b) => Math.hypot(a.rx - b.rx, a.ry - b.ry);
const hp = u => (u.hitPoints ?? 100) / (u.maxHitPoints || 100);
export const isAirSupport = r => r?.factory === 'AircraftType';

export function effectiveness(rule, targets, catalog, api) {
  const weapons = [rule?.weapon, rule?.deployer ? rule.secondary : undefined].filter(Boolean);
  const samples = targets.length ? targets : [{ type: api.ObjectType.Infantry }, { type: api.ObjectType.Vehicle }];
  return samples.reduce((sum, t) => sum + Math.max(0, ...weapons.map(w => {
    if (t.zone === (api.ZoneType?.Air ?? 1) ? !w.aa : w.ag === false) return 0;
    const armor = catalog[t.name]?.armor;
    const index = Object.entries(api.ArmorType ?? {}).find(([k, v]) => /^\d+$/.test(k) && String(v).toLowerCase() === armor)?.[0];
    const verses = index === undefined ? 1 : w.verses?.[index] ?? w.versus?.[index] ?? 1;
    return (w.damage || 0) * verses * 15 / (w.rof || 30) * Math.max(0.5, (w.range || 4) / 5);
  })), 0) / samples.length;
}

export function assessStrategy(api, catalog, snapshot, memory) {
  const { units, buildings, enemies, base } = snapshot.raw;
  const state = snapshot.state, tick = api.tick();
  const core = buildings.filter(b => !catalog[b.name]?.wall && !catalog[b.name]?.tickTank);
  const threats = enemies.filter(e => e.primaryWeapon && core.some(b => dist(e.tile, b.tile) < 18));
  const defenders = units.filter(u => u.primaryWeapon && !catalog[u.name]?.harvester && base && dist(u.tile, base.tile) < 24);
  memory.pressure ??= { since: tick, lastThreatTick: -10000 };
  const history = memory.pressure;
  if (threats.length) {
    if (tick - history.lastThreatTick > 450) history.since = tick;
    history.lastThreatTick = tick;
    history.approach = { rx: threats.reduce((s, u) => s + u.tile.rx, 0) / threats.length,
      ry: threats.reduce((s, u) => s + u.tile.ry, 0) / threats.length };
  }
  const ownPower = defenders.reduce((s, u) => s + effectiveness(catalog[u.name], threats, catalog, api) * hp(u), 0);
  const enemyPower = threats.reduce((s, u) => s + effectiveness(catalog[u.name], defenders, catalog, api) * hp(u), 0);
  const underPressure = threats.length > 0;
  const sustained = underPressure && tick - history.since > 450;
  const suppressed = underPressure && (sustained || threats.length >= 3 && enemyPower > ownPower * 0.8);
  const critical = core.some(b => hp(b) < 0.35 && threats.some(e => dist(e.tile, b.tile) < 8));
  const approach = tick - history.lastThreatTick < 1800 ? history.approach : undefined;
  state.strategy = { underPressure, sustained, suppressed, critical,
    pressureTicks: underPressure ? tick - history.since : 0,
    localStrengthEstimate: Math.round(ownPower), enemyStrengthEstimate: Math.round(enemyPower),
    enemyMix: { infantry: threats.filter(u => u.type === api.ObjectType.Infantry && u.zone !== 1).length,
      vehicles: threats.filter(u => u.type === api.ObjectType.Vehicle && u.zone !== 1).length,
      air: threats.filter(u => u.zone === 1).length },
    approach, reserve: 0, investment: null,
    intent: critical ? '保住核心建筑，紧急反制' : suppressed ? '防御设施稳住阵地，预留科技突破' : '维持经济，推进科技与合成部队' };
  memory.strategy = state.strategy;
  return state.strategy;
}

export function chooseBuildingSite(api, catalog, name, own, memory, limit = 200) {
  const buildings = own.filter(u => u.type === api.ObjectType.Building && !catalog[u.name]?.wall);
  const base = buildings.find(u => catalog[u.name]?.yard) ?? buildings[0];
  if (!base) return undefined;
  const r = catalog[name] ?? {}, approach = memory.strategy?.approach;
  const defense = r.isBaseDefense || r.wall;
  const vector = approach ? { x: approach.rx - base.tile.rx, y: approach.ry - base.tile.ry } : { x: 1, y: 1 };
  const length = Math.hypot(vector.x, vector.y) || 1;
  const offset = defense ? Math.min(6, length * 0.5) : -4;
  const desired = { rx: base.tile.rx + vector.x / length * offset, ry: base.tile.ry + vector.y / length * offset };
  const candidates = new Map();
  for (const anchor of buildings.slice(0, 12)) for (let dx = -10; dx <= 10; dx++) for (let dy = -10; dy <= 10; dy++) {
    const x = anchor.tile.rx + dx, y = anchor.tile.ry + dy;
    const tile = api.map.tile(x, y);
    if (!tile) continue;
    const p = { rx: x, ry: y };
    if (r.wall && buildings.some(b => catalog[b.name]?.factory && dist(b.tile, p) < 4)) continue;
    let score = -dist(p, desired) - dist(p, base.tile) * 0.15;
    if (approach && defense) {
      const range = r.weapon?.range || 4, enemyDistance = dist(p, approach);
      score += enemyDistance <= range + 2 ? 6 : -Math.max(0, enemyDistance - range - 2);
      if (enemyDistance < 2) score -= 12;
    }
    candidates.set(`${x},${y}`, { x, y, score });
  }
  for (const p of [...candidates.values()].sort((a, b) => b.score - a.score).slice(0, limit))
    if (api.canPlace(name, p.x, p.y)) return { x: p.x, y: p.y };
  return undefined;
}

export function investmentGroups(api, catalog, snapshot, memory, groups) {
  if (!api.QueueType || !api.canPlace) return;
  const { units, buildings, enemies } = snapshot.raw, s = snapshot.state, strategy = s.strategy;
  const available = api.production.available();
  const ownNames = new Set(buildings.map(u => u.name));
  const queue = type => s.queues.find(q => q.type === type);
  const free = type => { const q = queue(type); return q && !q.size && q.maxSize !== 0; };
  const group = (id, instructions) => groups[id] ??= { instructions, criteria: { wait: 'Wait only if the offered investment is unnecessary or unaffordable.' }, actions: { wait: { type: 'wait' } } };
  const add = (g, item, purpose, minCredits, placement) => {
    const r = catalog[item.name], key = `produce_${item.name}`;
    g.criteria[key] = `${purpose}: ${r.label}; cost ${r.cost}, technology level ${r.techLevel ?? 0}, power ${r.power ?? 0}, weapon range ${r.weapon?.range ?? 0}.`;
    g.actions[key] = { type: 'produce', name: item.name, queue: item.queue, cost: r.cost, minCredits, placement };
  };
  // Replace generic wall-first choices with actual counter-weapons and a firing position.
  const dg = groups.defenses = { instructions: 'Counter the observed attackers with static weapons at the supplied firing position. Build early under pressure, even with only one miner. Prefer effective weapons over walls. Replace lost defenses and expand the defensive line during sustained suppression; do not stop at two obsolete pillboxes. Reserve power. Walls are optional screens after guns cover the approach.', criteria: { wait: 'Wait when existing defenses cover the threat or when no effective defense is available.' }, actions: { wait: { type: 'wait' } } };
  const defenseUnits = buildings.filter(u => catalog[u.name]?.isBaseDefense && !catalog[u.name]?.wall);
  const targetDefenses = strategy.underPressure ? (strategy.suppressed ? 6 : 3) : 1;
  let defensePlan, coverage = 0;
  if (s.harvesters >= (strategy.underPressure ? 1 : 2) && free(api.QueueType.Armory)) {
    const options = api.production.available(api.QueueType.Armory).filter(i => catalog[i.name]?.isBaseDefense && !catalog[i.name]?.wall)
      .map(i => ({ ...i, queue: api.QueueType.Armory, value: effectiveness(catalog[i.name], enemies, catalog, api) }));
    coverage = defenseUnits.reduce((n, u) => n + (effectiveness(catalog[u.name], enemies, catalog, api) > 0 && (!strategy.approach || dist(u.tile, strategy.approach) < (catalog[u.name]?.weapon?.range ?? 4) + 5) ? 1 : 0), 0);
    if (coverage < targetDefenses && defenseUnits.length < 8) for (const item of options.sort((a, b) => b.value / Math.sqrt(catalog[b.name].cost) - a.value / Math.sqrt(catalog[a.name].cost)).slice(0, 2)) {
      if (item.value <= 0) continue;
      const r = catalog[item.name];
      if (r.power < 0 && (s.economy?.powerMargin ?? 0) < -r.power) continue;
      const placement = chooseBuildingSite(api, catalog, item.name, units, memory);
      if (!placement || s.self.credits < Math.min(200, r.cost)) continue;
      add(dg, item, `${strategy.underPressure ? 'URGENT' : 'PREPARE'}: counter-fire at (${placement.x},${placement.y}), estimated effectiveness ${Math.round(item.value)}`, Math.min(200, r.cost), placement);
      defensePlan ??= { name: item.name, cost: r.cost, queue: item.queue };
    }
    if (!strategy.underPressure && defenseUnits.length && s.uncommittedCredits > 1800 && buildings.filter(u => catalog[u.name]?.wall).length < 4) {
      const wall = api.production.available(api.QueueType.Armory).find(i => catalog[i.name]?.wall);
      if (wall) { const placement = chooseBuildingSite(api, catalog, wall.name, units, memory); if (placement) add(dg, { ...wall, queue: api.QueueType.Armory }, 'Screen a defended approach without blocking factory exits', catalog[wall.name].cost, placement); }
    }
  }
  const cg = group('construction', 'Restore core infrastructure, then unlock higher technology. During suppression, build a firing line and develop a counter instead of spending forever on basic tanks. Aircraft factories and higher-tech buildings unlock new options. A repair dock is not an airfield.');
  // Remove the old special-layer air-support guess and rebuild the tech options from rule categories.
  for (const [key, a] of Object.entries(cg.actions)) if (a.type === 'produce' && !catalog[a.name]?.naval && !catalog[a.name]?.refinery && !(catalog[a.name]?.power > 0) && !['InfantryType', 'UnitType', 'BuildingType'].includes(catalog[a.name]?.factory)) {
    delete cg.actions[key]; delete cg.criteria[key];
  }
  const armorCount = units.filter(u => u.type === api.ObjectType.Vehicle && catalog[u.name]?.category === 'AFV' && !catalog[u.name]?.harvester).length;
  const coreReady = s.harvesters >= 2 && s.economy?.factories > 0 && (armorCount >= 4 || strategy.suppressed && coverage >= 2);
  const candidates = available.filter(i => i.type === api.ObjectType.Building && !ownNames.has(i.name))
    .filter(i => { const r = catalog[i.name]; return r && !r.naval && !r.yard && !r.refinery && !r.isBaseDefense && !r.wall && !(r.power > 0) && (isAirSupport(r) || r.buildCategory === 'Tech' && !r.factory); })
    .sort((a, b) => Number(isAirSupport(catalog[b.name])) - Number(isAirSupport(catalog[a.name])) || (catalog[b.name].techLevel ?? 0) - (catalog[a.name].techLevel ?? 0));
  let techPlan;
  if (coreReady && free(api.QueueType.Structures) && !strategy.critical) {
    const item = candidates[0];
    if (item) {
      const r = catalog[item.name];
      techPlan = { name: item.name, cost: r.cost, queue: api.QueueType.Structures };
      if ((s.economy.powerMargin ?? 0) >= Math.max(0, -r.power) && s.self.credits >= Math.min(600, r.cost)) {
        add(cg, { ...item, queue: api.QueueType.Structures }, `${strategy.suppressed ? 'BREAK THE STALEMATE' : 'TECH ADVANCE'}: unlock stronger units, support and defenses; prerequisites ${r.prerequisite?.join(',') || 'already met'}`, Math.min(600, r.cost));
        cg.instructions += ' Prioritize the offered TECH ADVANCE/BREAK THE STALEMATE before duplicating a vehicle factory.';
      } else if ((s.economy.powerMargin ?? 0) < Math.max(0, -r.power)) {
        const power = api.production.available(api.QueueType.Structures).filter(i => catalog[i.name]?.power > 0).sort((a,b) => catalog[a.name].cost-catalog[b.name].cost)[0];
        if (power && s.self.credits >= 300) { techPlan = { name: power.name, cost: catalog[power.name].cost, queue: api.QueueType.Structures }; add(cg, {...power, queue:api.QueueType.Structures}, 'POWER FOR TECH: supply the planned technology and defenses',300); }
      }
    }
  }
  const urgentDefense = strategy.underPressure && coverage < (strategy.critical ? 6 : 2) && defensePlan;
  const plan = urgentDefense || techPlan || defensePlan;
  strategy.investment = plan;
  strategy.reserve = plan ? plan.cost + (strategy.critical ? 0 : 250) : 0;
  strategy.hasAirSupport = buildings.some(u => isAirSupport(catalog[u.name]));
  strategy.techChoices = candidates.map(i => i.name);
  memory.strategy = strategy;
  // The separate choice groups share one wallet. Protect the chosen capital budget.
  for (const [id, g] of Object.entries(groups)) for (const [key, a] of Object.entries(g.actions)) {
    if (a.type !== 'produce' || a.name === plan?.name) continue;
    const r = catalog[a.name] ?? {};
    const essential = id === 'construction' && (r.power > 0 || r.refinery && !s.economy.refineries || r.factory === 'UnitType' && !r.naval && !s.economy.factories);
    if (!essential && s.uncommittedCredits - a.cost < strategy.reserve) { delete g.actions[key]; delete g.criteria[key]; }
  }
  // Explain upgraded unit advantages to the model using current target armor, range and rules.
  for (const id of ['vehicles', 'infantry', 'aircraft', 'navy']) {
    const g = groups[id]; if (!g) continue;
    g.instructions += ' Compare effective damage against the current enemy mix, range and technology level. Use newly unlocked counters instead of repeating the cheapest basic unit.';
    for (const [key,a] of Object.entries(g.actions)) if (a.type === 'produce') g.criteria[key] += ` Tech ${catalog[a.name]?.techLevel ?? 0}; estimated current-target effectiveness ${Math.round(effectiveness(catalog[a.name], enemies, catalog, api))}.`;
  }
  if (groups.vehicles && s.harvesters >= 2 && armorCount < 4 && !strategy.investment) {
    groups.vehicles.instructions += ' URGENT: the base has fewer than four mobile armored units. Build the offered combat reinforcement now when affordable; do not wait for an unplanned future technology investment.';
    groups.vehicles.criteria.wait = 'Wait only while the queue is busy or none of these reinforcements is affordable. There is no reserved capital project now; an idle affordable queue leaves the base exposed.';
  }
  recoveryGroups(api, catalog, snapshot, groups);
  operationalGoals(api, catalog, snapshot, groups);
}

function operationalGoals(api, catalog, snapshot, groups) {
  const { units } = snapshot.raw, s = snapshot.state;
  const ground = units.filter(u => u.type === api.ObjectType.Vehicle && u.primaryWeapon && !catalog[u.name]?.harvester && !catalog[u.name]?.naval && catalog[u.name]?.category !== 'AirPower');
  const aircraft = units.filter(u => catalog[u.name]?.aircraft && u.type !== api.ObjectType.Building);
  const target = Math.min(24, Math.max(12, Math.ceil((s.nearbyEnemyCount ?? 0) * 1.5)));
  s.objective = 'Win this skirmish by finding and destroying the enemy base, not merely surviving near our own base.';
  s.forceGoal = { groundCombatVehicles: { current:ground.length, target }, aircraft:{current:aircraft.length,target:4},
    attackThreshold:8, enemyBaseKnown:!!s.knownEnemyBuildings?.length, reserve:s.strategy.reserve };
  s.decisionReadiness = {};
  for (const [id, queueType, current, desired] of [
    ['vehicles',api.QueueType.Vehicles,ground.length,target],['aircraft',api.QueueType.Aircrafts,aircraft.length,4],
  ]) {
    const g=groups[id]; if (!g) continue;
    const q=s.queues.find(q=>q.type===queueType);
    const candidates=Object.values(g.actions).filter(a=>a.type==='produce');
    const affordable=candidates.filter(a=>s.uncommittedCredits-a.cost>=s.strategy.reserve);
    const needed=current<desired;
    const blocked=s.strategy.recovery || s.harvesters<2 || q?.size>0 || !affordable.length;
    s.decisionReadiness[id]={queueIdle:!q?.size,current,target:desired,deficit:Math.max(0,desired-current),
      credits:s.self.credits,committedCredits:s.committedCredits,reserve:s.strategy.reserve,
      affordableCandidates:affordable.map(a=>a.name),waitingSupported:!needed||!!blocked};
    if (!needed || blocked) continue;
    g.instructions=id==='vehicles'
      ? `Choose the next vehicle to win by destroying the enemy base. Our attack force target is ${desired} ground combat vehicles, but only ${current} are present. The factory is idle and the listed affordableCandidates can be paid for after preserving ${s.strategy.reserve} credits for capital projects. Build a useful combat vehicle now to reach the force target. Prefer effective newly unlocked weapons and range; keep anti-air escorts. Waiting has no benefit while the army is below target and funds are plentiful.`
      : `Prepare a ${desired}-aircraft wing for scouting and concentrated strikes to find and destroy the enemy base. Only ${current} aircraft exist; the queue is idle and production is affordable after reservations. Build an offered aircraft now, even when enemies are out of sight. Use ready aircraft to scout or strike, and let empty aircraft rearm.`;
    g.criteria.wait=`Wait only if the queue is busy, no useful unit is affordable after the ${s.strategy.reserve}-credit reservation, or the ${desired}-unit force is already assembled. Current count ${current}, uncommitted credits ${s.uncommittedCredits}.`;
    for(const [key,a] of Object.entries(g.actions)) if(a.type==='produce')g.criteria[key]+=` Build-up deficit: ${desired-current}; this production advances the winning force, even without a currently visible enemy.`;
  }
}

function recoveryGroups(api, catalog, snapshot, groups) {
  const { units, buildings } = snapshot.raw, s = snapshot.state;
  const hasYard = buildings.some(u => catalog[u.name]?.yard);
  const refineryCount = buildings.filter(u => catalog[u.name]?.refinery).length;
  const miners = units.filter(u => catalog[u.name]?.harvester).length;
  if (hasYard && refineryCount && miners || !buildings.length) return;
  const builder = units.find(u => catalog[catalog[u.name]?.deploysInto]?.yard);
  const miner = refineryCount && !miners && api.production.available(api.QueueType.Vehicles).find(i => catalog[i.name]?.harvester);
  if (!hasYard && builder && !miner) return;
  const queue = miner ? api.QueueType.Vehicles : hasYard ? api.QueueType.Structures : api.QueueType.Vehicles;
  const candidate = miner || api.production.available(queue).find(i => hasYard ? catalog[i.name]?.refinery : catalog[catalog[i.name]?.deploysInto]?.yard);
  if (!candidate) return;
  const r = catalog[candidate.name];
  const category = queue === api.QueueType.Structures ? 'construction' : 'vehicles';
  const targetQueue = s.queues.find(q=>q.type===queue);
  const pending = targetQueue?.items.find(i=>i.name===candidate.name);
  const required = pending ? Math.max(0,pending.creditsEach-pending.creditsSpent) : r.cost;
  s.strategy.intent = miner ? '恢复矿车，解除收入中断' : hasYard ? '恢复矿场，解除收入中断' : '重建基地车，恢复建造能力';
  s.strategy.recovery = true;
  s.strategy.investment = {name:candidate.name,cost:required,queue,category};
  s.strategy.reserve = required;
  for (const g of Object.values(groups)) for (const [key,a] of Object.entries(g.actions)) if (a.type==='produce' && a.name!==candidate.name) {
    delete g.actions[key]; delete g.criteria[key];
  }
  if (!targetQueue?.size && s.self.credits >= Math.min(500,required)) {
    const key=`recover_${candidate.name}`;
    groups[category].criteria[key]=`SURVIVAL: rebuild ${r.label} to restore ${miner || hasYard?'ore income':'construction'}. Cost ${r.cost}; stop discretionary investment until recovery completes.`;
    groups[category].actions[key]={type:'produce',name:candidate.name,queue,cost:r.cost,minCredits:Math.min(500,required)};
  }
  if (s.self.credits >= required) return;
  const g=groups.salvage ??= {instructions:'Recover a destroyed economy or construction capability. Cancel discretionary spending and sell expendable technology to fund recovery. Preserve the factory and all prerequisites needed to rebuild.',criteria:{wait:'Wait only when no safe liquidation is available.'},actions:{wait:{type:'wait'}}};
  g.instructions='URGENT ECONOMIC RECOVERY: income or construction is gone and recovery is underfunded. Cancel optional spending or sell a nonessential technology building. Keeping unused high technology without a functioning miner-and-refinery chain will lose the match. Preserve recovery prerequisites.';
  for (const q of s.queues) for (const item of q.items) if (item.name!==candidate.name && item.creditsSpent>0) {
    const key=`cancel_${item.name}`;
    g.criteria[key]=`Cancel ${item.name}, releasing its ${item.creditsSpent} paid credits to fund ${candidate.name}.`;
    g.actions[key]={type:'cancel',name:item.name,queue:q.type};
  }
  for (const b of buildings) {
    const rule=catalog[b.name];
    if (!rule || rule.unsellable || rule.yard || rule.refinery || rule.power>0 || rule.factory==='UnitType' || r.prerequisite?.includes(b.name) || b.garrison?.count) continue;
    const key=`recover_sell_${b.id}`;
    g.criteria[key]=`Sell expendable ${rule.label} #${b.id} to finance ${candidate.name}; original cost ${rule.cost}.`;
    g.actions[key]={type:'sell',objectId:b.id};
  }
}
