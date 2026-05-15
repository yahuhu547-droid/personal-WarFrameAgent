import json, re

with open('data/riven_weapons.json', 'r') as f:
    riven_names = set(json.load(f))
with open('data/item_aliases.json', 'r', encoding='utf-8-sig') as f:
    manual = json.load(f)
with open('data/generated_aliases.json', 'r', encoding='utf-8-sig') as f:
    generated = json.load(f)
with open('data/items_full.json', 'r', encoding='utf-8') as f:
    items_full = json.load(f)

def norm(v):
    return re.sub(r'[^a-z0-9]', '', v.lower())

VARIANT_PREFIXES = [
    'sancti_', 'vaykor_', 'prisma_', 'wraith_', 'vandal_',
    'mutalist_', 'kuva_', 'tenet_', 'dex_',
    'secura_', 'rakta_', 'detonite_', 'telos_', 'cobra_',
]

def is_cjk(c):
    return '一' <= c <= '鿿'

# === 1. generated_aliases.json 中指向变体武器的中文别名
gen_variant_aliases = []
for alias, target in generated.items():
    has_cjk = any(is_cjk(c) for c in alias)
    if not has_cjk:
        continue
    if any(norm(target).startswith(p) for p in VARIANT_PREFIXES):
        gen_variant_aliases.append({'alias': alias, 'target': target})

# === 2. items_full.json 中指向变体武器的中文名
dict_variants = []
for item in items_full:
    item_id = item.get('item_id', '')
    zh_name = item.get('zh_name', '')
    if zh_name and any(norm(item_id).startswith(p) for p in VARIANT_PREFIXES):
        base = norm(item_id)
        for p in VARIANT_PREFIXES:
            if base.startswith(p):
                base = base[len(p):]
                break
        dict_variants.append({
            'zh_name': zh_name,
            'variant_id': item_id,
            'base': base,
            'base_in_riven': base in riven_names,
        })

# === 3. 找出所有可能与变体混淆的中文别名
# 规则：generated_alias 中有一个中文别名 -> 变体武器（比如"圣洁执法者" -> sancti_magistar）
# 但同时，基础武器也有一个中文名（"执法者" -> magistar）
# 如果用户输入"执法者紫卡"，resolver 可能匹配到 sancti_magistar

# 构建基础武器的中文名映射
base_zh_names = {}
for item in items_full:
    item_id = item.get('item_id', '')
    zh_name = item.get('zh_name', '')
    if zh_name and not any(norm(item_id).startswith(p) for p in VARIANT_PREFIXES):
        base_zh_names[zh_name] = item_id

# === 4. 关键问题检查：generated_aliases.json 中哪些变体武器别名
# 与基础武器的中文名相似（可能导致"武器紫卡"歧义）
conflict_report = []
for alias, target in generated.items():
    has_cjk = any(is_cjk(c) for c in alias)
    if not has_cjk:
        continue
    if not any(norm(target).startswith(p) for p in VARIANT_PREFIXES):
        continue
    # 这个别名指向变体武器，检查基础武器中文名是否是这个别名的子串
    # 例如：alias="圣洁执法者" target="sancti_magistar"
    # 基础武器是magistar，中文名可能是"执法者"
    base = norm(target)
    for p in VARIANT_PREFIXES:
        if base.startswith(p):
            base = base[len(p):]
            break
    # 检查是否有基础武器叫这个别名（去掉变体前缀）
    # 例如：如果别名是"执法者"，检查基础武器的中文名是否也是"执法者"
    # 这是正常的——如果别名恰好等于基础武器中文名，就有歧义
    base_matches = [zh for zh, bid in base_zh_names.items()
                    if norm(bid) == base and any(is_cjk(c) for c in zh)]
    if base_matches:
        conflict_report.append({
            'alias': alias,
            'target': target,
            'base': base,
            'base_zh_names': base_matches,
            'note': 'AMBIGUOUS - alias same as base weapon Chinese name'
        })

# === 5. 也检查 item_aliases.json 中的类似问题
alias_conflicts = []
for alias, target in manual.items():
    has_cjk = any(is_cjk(c) for c in alias)
    if not has_cjk:
        continue
    if not any(norm(target).startswith(p) for p in VARIANT_PREFIXES):
        continue
    base = norm(target)
    for p in VARIANT_PREFIXES:
        if base.startswith(p):
            base = base[len(p):]
            break
    base_matches = [zh for zh, bid in base_zh_names.items()
                    if norm(bid) == base and any(is_cjk(c) for c in zh)]
    if base_matches:
        alias_conflicts.append({
            'alias': alias,
            'target': target,
            'base': base,
            'base_zh_names': base_matches,
        })

# === 6. 检查所有紫卡武器中，哪些变体武器有紫卡但别名指向基础武器
# 这种情况正好相反：别名->基础武器（正确），但字典可能返回变体
# 从紫卡API看哪些变体武器有紫卡
print('=== 紫卡武器中，哪些变体武器也有紫卡 ===')
for wpn in sorted(riven_names):
    if any(norm(wpn).startswith(p) for p in VARIANT_PREFIXES):
        base = norm(wpn)
        for p in VARIANT_PREFIXES:
            if base.startswith(p):
                base = base[len(p):]
                break
        base_has_riven = base in riven_names
        print(f'  {wpn!r} (base: {base!r}, base has riven: {base_has_riven})')

# 保存完整报告
report = {
    'gen_variant_aliases': gen_variant_aliases,
    'dict_variants': dict_variants,
    'generated_conflicts': conflict_report,
    'alias_conflicts': alias_conflicts,
}
with open('data/riven_variant_report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print('\n报告已保存到 data/riven_variant_report.json')
print(f'Generated中指向变体的中文别名: {len(gen_variant_aliases)}')
print(f'字典中指向变体的中文名: {len(dict_variants)}')
print(f'Generated别名歧义冲突: {len(conflict_report)}')
print(f'Alias别名歧义冲突: {len(alias_conflicts)}')