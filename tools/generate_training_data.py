"""从现有知识库生成合成训练数据。"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def load_aliases() -> dict[str, str]:
    aliases = {}
    for path in [DATA_DIR / "item_aliases.json", DATA_DIR / "generated_aliases.json"]:
        if path.exists():
            with path.open("r", encoding="utf-8-sig") as f:
                aliases.update(json.load(f))
    return aliases


def generate_alias_qa(aliases: dict[str, str]) -> list[dict]:
    pairs = []
    for alias, item_id in aliases.items():
        pairs.append({
            "messages": [
                {"role": "system", "content": "你是 Warframe 交易助手。识别物品名称并给出 market_id。"},
                {"role": "user", "content": f"{alias}是什么物品？"},
                {"role": "assistant", "content": f"{alias} 对应的 market_id 是 {item_id}。"},
            ]
        })
        pairs.append({
            "messages": [
                {"role": "system", "content": "你是 Warframe 交易助手。"},
                {"role": "user", "content": f"查一下{alias}的价格"},
                {"role": "assistant", "content": f"好的，我来查询 {alias} ({item_id}) 的市场价格。"},
            ]
        })
    return pairs


def generate_intent_qa() -> list[dict]:
    templates = [
        ("我要买{item}", "看起来你想购买 {item}，让我帮你查最低卖价。"),
        ("{item}能卖多少", "你想出售 {item}，让我查最高收价。"),
        ("{item}价差多少", "让我查看 {item} 的买卖价差。"),
        ("{item}一套多少钱", "让我查询 {item} Prime 套装的完整价格。"),
        ("{item}趋势怎么样", "让我查看 {item} 的近期价格走势。"),
    ]
    sample_items = ["充沛", "川流不息", "优雅", "Rhino Prime", "Mesa Prime"]
    pairs = []
    for template, response in templates:
        for item in sample_items:
            pairs.append({
                "messages": [
                    {"role": "system", "content": "你是资深 Warframe 交易助手。"},
                    {"role": "user", "content": template.format(item=item)},
                    {"role": "assistant", "content": response.format(item=item)},
                ]
            })
    return pairs


def generate_comparison_qa() -> list[dict]:
    comparisons = [
        ("充沛", "优雅", "赋能"),
        ("Rhino Prime", "Mesa Prime", "战甲"),
        ("川流不息", "濒死理智", "MOD"),
    ]
    pairs = []
    for item_a, item_b, category in comparisons:
        pairs.append({
            "messages": [
                {"role": "system", "content": "你是资深 Warframe 交易助手，擅长价格分析。"},
                {"role": "user", "content": f"帮我对比{item_a}和{item_b}的价格"},
                {"role": "assistant", "content": f"好的，我来分别查询 {item_a} 和 {item_b} 的价格并进行对比分析。"},
            ]
        })
    return pairs


def main():
    aliases = load_aliases()
    all_pairs = []
    all_pairs.extend(generate_alias_qa(aliases))
    all_pairs.extend(generate_intent_qa())
    all_pairs.extend(generate_comparison_qa())

    output_path = DATA_DIR / "training_data_synthetic.jsonl"
    with output_path.open("w", encoding="utf-8") as f:
        for pair in all_pairs:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")
    print(f"Generated {len(all_pairs)} training examples -> {output_path}")


if __name__ == "__main__":
    main()
