import json, re

with open('data/riven_weapons.json', 'r') as f:
    riven_names = set(json.load(f))
with open('data/generated_aliases.json', 'r', encoding='utf-8-sig') as f:
    generated = json.load(f)

def norm(v):
    return re.sub(r'[^a-z0-9]', '', v.lower())

VARIANT_PREFIXES = [
    'sancti_', 'vaykor_', 'prisma_', 'wraith_', 'vandal_',
    'mutalist_', 'kuva_', 'tenet_', 'dex_',
    'secura_', 'rakta_', 'detonite_', 'telos_', 'cobra_',
]

# === 直接检查圣洁执法者系列 ===
print('=== 圣洁执法者系列 ===')
for k, v in generated.items():
    if 'magistar' in v.lower():
        has_cjk = any('一' <= c <= '鿿' for c in k)
        is_var = any(norm(v).startswith(p) for p in VARIANT_PREFIXES)
        base = norm(v)
        for p in VARIANT_PREFIXES:
            if base.startswith(p):
                base = base[len(p):]
                break
        print(f'  {k!r} -> {v!r} cjk={has_cjk} is_variant={is_var} base={base!r} base_in_riven={base in riven_names}')

# === 找所有指向变体武器的中文别名 ===
print('\n=== 所有指向变体武器的中文别名 ===')
for k, v in generated.items():
    has_cjk = any('一' <= c <= '鿿' for c in k)
    if not has_cjk:
        continue
    if not any(norm(v).startswith(p) for p in VARIANT_PREFIXES):
        continue
    base = norm(v)
    for p in VARIANT_PREFIXES:
        if base.startswith(p):
            base = base[len(p):]
            break
    print(f'  {k!r} -> {v!r} base={base!r} base_in_riven={base in riven_names}')

# === 检查 magi star 是否在紫卡列表 ===
print('\n=== magistrate 关键检查 ===')
print('magistar in riven:', 'magistar' in riven_names)
print('sancti_magistar in riven:', 'sancti_magistar' in riven_names)
print('hek in riven:', 'hek' in riven_names)

# 打印紫卡列表中所有 melee 武器
print('\n=== 紫卡列表中的近战武器 ===')
melee = [w for w in riven_names if any(w.startswith(p) for p in VARIANT_PREFIXES)]
for w in sorted(melee):
    print(f'  {w}')

# === 打印紫卡列表中所有 mag* 武器 ===
print('\n=== 紫卡列表中 mag* 武器 ===')
for w in sorted(riven_names):
    if w.startswith('mag'):
        print(f'  {w}')