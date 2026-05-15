"""紫卡武器别名全面检查脚本。"""
import json, re

# 加载紫卡武器名（从 warframe.market API 获取）
with open('data/riven_weapons.json', 'r') as f:
    riven_names = set(json.load(f))
print(f'紫卡API武器数: {len(riven_names)}')

# 加载所有别名
with open('data/item_aliases.json', 'r', encoding='utf-8-sig') as f:
    manual = json.load(f)
with open('data/generated_aliases.json', 'r', encoding='utf-8-sig') as f:
    generated = json.load(f)

def norm(v):
    return re.sub(r'[^a-z0-9]', '', v.lower())

# 变体前缀列表（这些前缀的武器在紫卡API中没有，需要用基础版）
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

# 1. 找 generated_aliases.json 中指向变体武器的中文别名（且基础版有紫卡）
print('\n=== generated_aliases.json 中中文别名指向变体武器的情况 ===')
gen_problems = []
for alias, target in generated.items():
    has_chinese = any('一' <= c <= '鿿' for c in alias)
    if not has_chinese:
        continue
    if is_variant(target):
        base = get_base(target)
        base_in_riven = base in riven_names
        if base_in_riven:
            gen_problems.append((alias, target, base))
            print(f'  修正: {alias!r:20} -> {target!r:30} (改为: {base!r})')
        else:
            print(f'  OK(无基础版): {alias!r:20} -> {target!r:30}')

print(f'\ngenerated 中需修正: {len(gen_problems)} 条')

# 2. 找 item_aliases.json 中指向变体武器的别名
print('\n=== item_aliases.json 中指向变体武器的别名 ===')
alias_problems = []
for alias, target in manual.items():
    if is_variant(target):
        base = get_base(target)
        base_in_riven = base in riven_names
        if base_in_riven:
            alias_problems.append((alias, target, base))
            print(f'  修正: {alias!r:30} -> {target!r:30} (改为: {base!r})')

print(f'\nitem_aliases.json 中需修正: {len(alias_problems)} 条')

# 3. 从 items_full.json 检查哪些中文名对应变体武器
print('\n=== items_full.json：哪些变体武器有对应基础版 ===')
with open('data/items_full.json', 'r', encoding='utf-8') as f:
    items_full = json.load(f)

variant_zh_names = []
for item in items_full:
    item_id = item.get('item_id', '')
    if is_variant(item_id) and item.get('zh_name'):
        base = get_base(item_id)
        base_in_riven = base in riven_names
        variant_zh_names.append((item['zh_name'], item_id, base, base_in_riven))
        if base_in_riven:
            print(f'  有紫卡: {item["zh_name"]!r:20} -> {item_id!r:30} (基础版: {base!r})')

print(f'\n变体武器中文名(基础有紫卡): {sum(1 for _,_,_,b in variant_zh_names if b)} 条')

# 4. 汇总：哪些中文别名可能让用户误解为"武器紫卡"
print('\n=== 潜在问题：中文别名可能被用户用作紫卡武器名 ===')
potential = []
# 检查 item_aliases.json 中的所有中文别名
for alias, target in manual.items():
    has_chinese = any('一' <= c <= '鿿' for c in alias)
    if not has_chinese:
        continue
    t_clean = norm(target)
    # 如果别名本身就是武器名（如"执法者"），但指向了变体
    if is_variant(target):
        base = get_base(target)
        if base in riven_names:
            potential.append((alias, target, base, '指向变体(需改基础版)'))
    elif t_clean not in riven_names:
        # 别名指向的武器不在紫卡列表中
        if not any(t_clean.endswith(s) for s in ['_set', '_mod', '_blueprint', '_chassis', '_systems', '_neuroptics']):
            potential.append((alias, target, t_clean, '目标不在紫卡列表'))

# 过滤掉明显的非武器
for item in potential[:30]:
    print(f'  {item}')

print(f'\n共 {len(potential)} 个潜在问题项（已过滤非武器）')

# 5. 保存详细报告
report = {
    'riven_weapons_count': len(riven_names),
    'riven_weapons_sample': sorted(list(riven_names))[:50],
    'generated_alias_problems': [(a, t, b) for a, t, b in gen_problems],
    'manual_alias_problems': [(a, t, b) for a, t, b in alias_problems],
    'potential_problems': [(a, t, b, note) for a, t, b, note in potential],
}
with open('data/riven_weapon_check_report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print('\n报告已保存到 data/riven_weapon_check_report.json')