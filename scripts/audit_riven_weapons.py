"""紫卡武器别名系统性检查脚本 - 修复版（norm会去掉下划线）。"""
import json, re

with open('data/riven_weapons.json', 'r') as f:
    riven_names = set(json.load(f))
with open('data/item_aliases.json', 'r', encoding='utf-8-sig') as f:
    manual = json.load(f)
with open('data/generated_aliases.json', 'r', encoding='utf-8-sig') as f:
    generated = json.load(f)
with open('data/items_full.json', 'r', encoding='utf-8') as f:
    items = json.load(f)

def norm(v):
    return re.sub(r'[^a-z0-9]', '', v.lower())

# 变体前缀（注意：norm() 会把下划线去掉，所以 'sancti_magistar' -> 'sanctimagistar'）
VARIANT_PREFIXES_NORMED = [
    'sancti', 'vaykor', 'prisma', 'wraith', 'vandal',
    'mutalist', 'kuva', 'tenet', 'dex',
    'secura', 'rakta', 'detonite', 'telos', 'cobra',
]
# 变体前缀原始形式（用于显示）
VARIANT_PREFIXES_RAW = [
    'sancti_', 'vaykor_', 'prisma_', 'wraith_', 'vandal_',
    'mutalist_', 'kuva_', 'tenet_', 'dex_',
    'secura_', 'rakta_', 'detonite_', 'telos_', 'cobra_',
]

def get_base(name):
    """从变体武器名中提取基础版（norm后）。"""
    n = norm(name)
    for p in VARIANT_PREFIXES_NORMED:
        if n.startswith(p):
            # 去掉前缀，注意 norm 去掉了下划线
            # 但基础名本身可能包含下划线（如 'hec'）
            # 策略：去掉前缀部分后，在原始名中找对应的下划线位置
            raw_n = name.strip().lower()
            for rp, rp_n in zip(VARIANT_PREFIXES_RAW, VARIANT_PREFIXES_NORMED):
                if n.startswith(rp_n):
                    # 从原始名中截取
                    idx = raw_n.find(rp_n)
                    if idx >= 0:
                        return raw_n[idx + len(rp):]
                    # 如果没找到下划线版，直接截取
                    return name.strip().lower()[len(rp):]
    return n

def is_variant(name):
    n = norm(name)
    return any(n.startswith(p) for p in VARIANT_PREFIXES_NORMED)

SKIP_SUFFIXES = ['_set', '_mod', '_blueprint', '_chassis', '_systems',
                 '_neuroptics', '_blade', '_guard', '_handle', '_stock',
                 '_barrel', '_receiver', '_link', '_harness', '_wings']

# === 1. generated_aliases.json 中指向变体武器的中文别名（且基础版有紫卡）
print('=== 1. generated_aliases.json 中需要修正的变体别名 ===')
gen_fixes = []
for alias, target in generated.items():
    has_cjk = any('一' <= c <= '鿿' for c in alias)
    if not has_cjk:
        continue
    if not is_variant(target):
        continue
    base = get_base(target)
    base_norm = norm(base)
    if base_norm in riven_names:
        gen_fixes.append((alias, target, base))
        print(f'  {alias!r} -> {target!r} (应改为: {base!r})')

print(f'\ngenerated 中需修正: {len(gen_fixes)} 条')

# === 2. item_aliases.json 中指向变体武器的别名
print('\n=== 2. item_aliases.json 中需要修正的变体别名 ===')
alias_fixes = []
for alias, target in manual.items():
    if not is_variant(target):
        continue
    base = get_base(target)
    base_norm = norm(base)
    if base_norm in riven_names:
        alias_fixes.append((alias, target, base))
        print(f'  {alias!r} -> {target!r} (应改为: {base!r})')

print(f'\nitem_aliases.json 中需修正: {len(alias_fixes)} 条')

# === 3. items_full.json 中指向变体武器的中文名（可能导致歧义）
print('\n=== 3. items_full.json 中指向变体武器的中文名 ===')
dict_variants = []
for item in items:
    item_id = item.get('item_id', '')
    zh_name = item.get('zh_name', '')
    if not zh_name:
        continue
    if not is_variant(item_id):
        continue
    base = get_base(item_id)
    base_norm = norm(base)
    if base_norm in riven_names:
        dict_variants.append((zh_name, item_id, base))
        print(f'  {zh_name!r} -> {item_id!r} (基础版: {base!r})')

print(f'\nitems_full 中变体中文名(基础有紫卡): {len(dict_variants)} 个')

# === 4. 紫卡列表中的变体武器（基础版也在紫卡列表中）
print('\n=== 4. 紫卡列表中的变体武器（基础版也有紫卡）===')
riven_variants = []
for wpn in sorted(riven_names):
    if is_variant(wpn):
        base = get_base(wpn)
        base_norm = norm(base)
        if base_norm in riven_names:
            riven_variants.append((wpn, base))
            print(f'  {wpn!r} (基础版: {base!r})')

print(f'\n紫卡列表中变体武器(基础也有): {len(riven_variants)} 个')

# === 5. 紫卡武器在别名中的缺失
print('\n=== 5. 紫卡武器在别名中的缺失 ===')
all_alias_targets = {norm(t) for t in {**manual, **generated}.values()}
missing_aliases = []
for wpn in sorted(riven_names):
    if wpn not in all_alias_targets:
        missing_aliases.append(wpn)

print(f'紫卡武器没有别名指向: {len(missing_aliases)} 个')
for w in missing_aliases[:20]:
    print(f'  {w}')
if len(missing_aliases) > 20:
    print(f'  ... 还有 {len(missing_aliases)-20} 个')

# === 6. 特别检查：哪些紫卡武器在 generated_aliases.json 中
# 有对应的中文别名指向了变体武器（导致搜索失败）
print('\n=== 6. 紫卡武器在 generated_aliases 中的中文别名问题 ===')
for alias, target in generated.items():
    has_cjk = any('一' <= c <= '鿿' for c in alias)
    if not has_cjk:
        continue
    t_norm = norm(target)
    if t_norm in riven_names:
        # 别名指向的武器在紫卡列表中
        # 但如果 target 是变体武器（如 sancti_magistar），就错了
        if is_variant(target):
            base = get_base(target)
            base_norm = norm(base)
            if base_norm in riven_names:
                print(f'  问题: {alias!r} -> {target!r}')
                print(f'    (应该指向基础版: {base!r})')

# 保存完整报告
report = {
    'generated_needs_fix': [(a, t, b) for a, t, b in gen_fixes],
    'manual_needs_fix': [(a, t, b) for a, t, b in alias_fixes],
    'dict_variants': [(a, t, b) for a, t, b in dict_variants],
    'riven_variants': [(a, b) for a, b in riven_variants],
    'missing_aliases': missing_aliases,
}
with open('data/riven_weapon_audit.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print('\n报告已保存到 data/riven_weapon_audit.json')