/** Player-side interpretation of effective, public match rules. */
export function refreshCatalog(api, catalog) {
  if (!api.rules) return catalog;
  const items = [...api.production.available(), ...api.units('self'), ...api.units('hostile')];
  const pending = [...items];
  const seen = new Set();
  for (let i = 0; i < pending.length; i++) {
    const { name, type } = pending[i];
    if (seen.has(`${type}:${name}`)) continue;
    seen.add(`${type}:${name}`);
    const rule = api.rules(name, type);
    if (!rule) continue;
    const weapon = (w) => w ? { ...w, verses: Object.assign([], w.versus) } : { damage: 0, range: 0, aa: false, ag: false, verses: [] };
    catalog[name] = {
      ...rule,
      factory: api.FactoryType[rule.factory] === 'None' ? undefined : api.FactoryType[rule.factory],
      buildCategory: api.BuildCat[rule.buildCat],
      armor: api.ArmorType[rule.armor].toLowerCase(),
      yard: rule.constructionYard,
      weapon: weapon(rule.primary), secondary: weapon(rule.secondary),
      aircraft: type === api.ObjectType.Aircraft,
    };
    if (rule.deploysInto) pending.push({ name: rule.deploysInto, type: api.ObjectType.Building });
    if (rule.undeploysInto) pending.push({ name: rule.undeploysInto, type: api.ObjectType.Vehicle });
    if (rule.freeUnit) pending.push({ name: rule.freeUnit, type: api.ObjectType.Vehicle });
  }
  return catalog;
}
