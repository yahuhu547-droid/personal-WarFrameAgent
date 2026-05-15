import json, re, sys

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

# 只关心指向武器别名（非部件/非mod）
weapon_aliases = {}
for alias, target in {**manual, **generated}.items():
    t = norm(target)
    if any(t.endswith(s) for s in SKIP_SUFFIXES):
        continue
    weapon_aliases[alias] = target

# 找出别名指向的武器不在紫卡列表、且不是变体的情况
problems = []
for alias, target in weapon_aliases.items():
    t = norm(target)
    if t in riven_names:
        continue  # OK
    if is_variant(target):
        base = get_base(target)
        if base in riven_names:
            problems.append((alias, target, base, 'variant_should_use_base'))
        continue
    # 目标不在紫卡列表
    problems.append((alias, target, t, 'target_not_in_riven'))

# 去重（按target去重，保留任意一个别名）
seen = {}
for alias, target, t_clean, note in problems:
    if t_clean not in seen or note == 'variant_should_use_base':
        seen[t_clean] = (alias, target, t_clean, note)

results = sorted(seen.values())

with open('data/riven_weapon_check_result.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# 统计
variant_issues = [(a, t, b) for a, t, b, n in results if n == 'variant_should_use_base']
weapon_not_in_riven = [(a, t, b) for a, t, b, n in results if n == 'target_not_in_riven']

print(f'Variant issues (alias -> syndicate, but base has riven): {len(variant_issues)}')
for a, t, b in variant_issues:
    print(f'  {a!r} -> {t!r} (should be: {b!r})')

print(f'\nWeapon not in riven list: {len(weapon_not_in_riven)}')
# 分类统计
categories = {}
for a, t, b, note in weapon_not_in_riven:
    if any(x in t for x in ['prime', 'prime_set']):
        cat = 'prime_set'
    elif '_weapon' in t:
        cat = 'weapon_component'
    else:
        cat = 'other'
    categories.setdefault(cat, []).append((a, t))

for cat, items in sorted(categories.items()):
    print(f'  Category {cat}: {len(items)} items')
    for a, t in items[:5]:
        print(f'    {a!r} -> {t!r}')
    if len(items) > 5:
        print(f'    ... and {len(items)-5} more')