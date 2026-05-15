import json, re

with open('data/riven_weapons.json', 'r') as f:
    riven_names = set(json.load(f))
with open('data/item_aliases.json', 'r', encoding='utf-8-sig') as f:
    manual = json.load(f)
with open('data/generated_aliases.json', 'r', encoding='utf-8-sig') as f:
    generated = json.load(f)

def norm(v):
    return re.sub(r'[^a-z0-9]', '', v.lower())

VARIANT_PREFIXES = [
    'sancti_', 'vaykor_', 'prisma_', 'wraith_', 'vandal_',
    'mutalist_', 'kuva_', 'tenet_', 'dex_',
    'secura_', 'rakta_', 'detonite_', 'telos_', 'cobra_',
]

def get_base(name):
    n = norm(name)
    for p in VARIANT_PREFIXES:
        if n.startswith(p):
            return n[len(p):]
    return n

def is_variant(name):
    n = norm(name)
    return any(n.startswith(p) for p in VARIANT_PREFIXES)

SKIP_SUFFIXES = ['_set', '_mod', '_blueprint', '_chassis', '_systems',
                 '_neuroptics', '_blade', '_guard', '_handle', '_stock',
                 '_barrel', '_receiver', '_link']

weapon_aliases = {}
for alias, target in {**manual, **generated}.items():
    t = norm(target)
    if any(t.endswith(s) for s in SKIP_SUFFIXES):
        continue
    weapon_aliases[alias] = target

problems = []
for alias, target in weapon_aliases.items():
    t = norm(target)
    if t in riven_names:
        continue
    if is_variant(target):
        base = get_base(target)
        if base in riven_names:
            problems.append({'alias': alias, 'target': target, 'base': base, 'note': 'variant_should_use_base'})
        continue
    problems.append({'alias': alias, 'target': target, 'base': t, 'note': 'target_not_in_riven'})

# 去重（按target去重）
seen = {}
for p in problems:
    k = p['base']
    if k not in seen or p['note'] == 'variant_should_use_base':
        seen[k] = p

results = sorted(seen.values(), key=lambda x: (x['note'], x['alias']))

variant_issues = [p for p in results if p['note'] == 'variant_should_use_base']
not_in_riven = [p for p in results if p['note'] == 'target_not_in_riven']

print(f'Variant issues (alias -> syndicate, but base has riven): {len(variant_issues)}')
for p in variant_issues:
    print(f'  {p["alias"]!r} -> {p["target"]!r} (should be: {p["base"]!r})')

print(f'\nWeapon not in riven list: {len(not_in_riven)}')

# 分类
categories = {'prime_set': [], 'warframe_parts': [], 'archwing': [], 'sentinel': [], 'other': []}
for p in not_in_riven:
    t = p['target']
    alias = p['alias']
    if any(x in t for x in ['prime_set', 'prime_chassis', 'prime_systems', 'prime_neuroptics', 'prime_blueprint']):
        categories['prime_set'].append(p)
    elif any(x in t for x in ['warframe', 'chassis', 'neuroptics', 'systems']):
        categories['warframe_parts'].append(p)
    elif any(x in t for x in ['archwing', 'moa']):
        categories['archwing'].append(p)
    elif any(x in t for x in ['sentinel', 'sentinel_']):
        categories['sentinel'].append(p)
    else:
        categories['other'].append(p)

for cat, items in sorted(categories.items(), key=lambda x: -len(x[1])):
    if items:
        print(f'\n  [{cat}] {len(items)} items:')
        for p in items[:8]:
            print(f'    {p["alias"]!r} -> {p["target"]!r}')
        if len(items) > 8:
            print(f'    ... and {len(items)-8} more')

# 单独看那些可能是武器但不在紫卡列表的
print('\n\n=== 可能是武器但不在紫卡列表（需人工审核）===')
# 过滤掉明显的非武器
suspicious = []
for p in not_in_riven:
    t = p['target']
    a = p['alias']
    # 排除已知类别
    is_prime_set = any(x in t for x in ['prime_set', 'prime_'])
    is_warframe_part = any(x in t for x in ['_chassis', '_systems', '_neuroptics', '_blueprint', '_harness', '_wings'])
    is_mod = any(x in t for x in ['_mod', 'primed_', 'vandal', 'wraith_relic', 'relic', 'arcane', 'sentinel', 'sentinel_', 'kavat', 'kubrow'])
    is_scene = any(x in t for x in ['_scene', '_decor', '_fan', '_bundle', 'neural', 'sigil', 'skin', 'helmet', 'earball', 'connector'])
    if not (is_prime_set or is_warframe_part or is_mod or is_scene):
        suspicious.append(p)

print(f'{len(suspicious)} items')
for p in suspicious[:30]:
    print(f'  {p["alias"]!r} -> {p["target"]!r}')

with open('data/riven_suspicious_weapons.json', 'w', encoding='utf-8') as f:
    json.dump(suspicious, f, ensure_ascii=False, indent=2)
print('\nSuspicious list saved to data/riven_suspicious_weapons.json')