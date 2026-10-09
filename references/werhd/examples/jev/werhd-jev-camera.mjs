// Spectator direction is entirely player-side policy. The engine only moves the local view.
const distance = (a, b) => Math.hypot(a.rx - b.rx, a.ry - b.ry);
export function updateCamera(api, catalog, memory, emit, now = performance.now()) {
  if (!memory.autoCamera || !api.camera) return;
  const own = api.units('self'), enemies = api.units('enemy');
  const base = own.find(u => catalog[u.name]?.yard) ?? own.find(u => u.type === api.ObjectType.Building);
  const previous = memory.cameraDirector;
  if (previous && now - previous.at < 5000) return;
  const engagements = enemies.filter(e => e.primaryWeapon && own.some(u => (u.primaryWeapon || catalog[u.name]?.yard) && distance(u.tile, e.tile) < 12));
  const battle = engagements.sort((a,b) => base ? distance(a.tile,base.tile)-distance(b.tile,base.tile) : a.id-b.id)[0];
  const placed = memory.lastPlaced && api.tick() - memory.lastPlaced.tick < 240 ? memory.lastPlaced : undefined;
  const scout = memory.mission?.ids.map(id=>own.find(u=>u.id===id)).find(Boolean);
  const point = battle?.tile ?? (placed && {rx:placed.x,ry:placed.y}) ?? scout?.tile ?? base?.tile;
  if (!point) return;
  const reason = battle ? '观察交战' : placed ? '观察新建筑' : scout ? '跟随部队任务' : '观察基地';
  if (previous && Math.hypot(point.rx-previous.x,point.ry-previous.y)<4 && reason===previous.reason) return;
  if (api.camera.centerAt(point.rx,point.ry)) {
    memory.cameraDirector = { at:now,x:point.rx,y:point.ry,reason };
    emit({ kind:'camera',tick:api.tick(),description:reason,x:point.rx,y:point.ry });
  }
}
