/**
 * 用户侧示例：在游戏页里直接调 window.werhd。
 * 这不是内置 AI，只是一份可粘贴 / 可 import 的参考脚本。
 *
 * 进局后控制台：
 *   const { attachWerhdPlayer } = await import('/docs/examples/werhd-user-script.mjs')
 *   attachWerhdPlayer(werhd)
 *
 * 默认用写死规则（展开基地车 → 造 E1 → 打看得见的敌人）。
 * 若要问 Jev，自己传入 askJev(snapshot)，不要在 onTick 里 await。
 */

export const MCV_NAMES = ['AMCV', 'SMCV', 'CMCV'];

export function snapshotFrom(werhd) {
  return {
    tick: werhd.tick?.() ?? 0,
    me: werhd.me?.(),
    units: werhd.units?.('self') ?? [],
    enemies: werhd.units?.('enemy') ?? [],
    available: werhd.production?.available?.() ?? [],
    queues: werhd.production?.queues?.() ?? [],
  };
}

export function decide(snapshot) {
  const units = snapshot.units ?? [];
  const enemies = snapshot.enemies ?? [];
  const mcv = units.find((unit) => MCV_NAMES.includes(unit.name));
  if (mcv) return { deployIds: [mcv.id] };

  const infantryQueue = (snapshot.queues ?? []).find((queue) => queue.type === 2);
  const queuedE1 = infantryQueue?.items?.some((item) => item.name === 'E1');
  const e1s = units.filter((unit) => unit.name === 'E1');
  const canMakeE1 = (snapshot.available ?? []).some((rule) => rule.name === 'E1');
  if (canMakeE1 && e1s.length === 0 && !queuedE1) return { produce: 'E1' };

  const idle = e1s.filter((unit) => unit.isIdle);
  const enemy = enemies[0];
  if (idle.length && enemy) return { attackIds: idle.map((unit) => unit.id), targetId: enemy.id };

  return {};
}

export function applyDecision(werhd, decision) {
  if (!decision) return;
  if (decision.deployIds?.length) werhd.deploy(decision.deployIds);
  if (decision.produce) werhd.produce(decision.produce);
  if (decision.attackIds?.length && decision.targetId != null) {
    werhd.attack(decision.attackIds, decision.targetId);
  }
}

export function attachWerhdPlayer(werhd, options = {}) {
  if (!werhd) throw new Error('werhd is not available');
  const askJev = options.askJev;
  const everyTicks = options.everyTicks ?? 10;
  let pending;
  let asking = false;

  werhd.onTick(({ tick }) => {
    if (pending) {
      applyDecision(werhd, pending);
      pending = undefined;
    }
    if (tick % everyTicks !== 0 || asking) return;
    const snapshot = snapshotFrom(werhd);
    if (!askJev) {
      applyDecision(werhd, decide(snapshot));
      return;
    }
    asking = true;
    Promise.resolve(askJev(snapshot))
      .then((answer) => {
        pending = answer;
      })
      .catch((error) => {
        console.error('werhd player askJev failed', error);
      })
      .finally(() => {
        asking = false;
      });
  });

  return { decide, applyDecision, snapshotFrom };
}

if (typeof globalThis !== 'undefined' && globalThis.werhd && globalThis.werhdAutoAttach !== false) {
  attachWerhdPlayer(globalThis.werhd);
}
