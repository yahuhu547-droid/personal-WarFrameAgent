from __future__ import annotations

import json
from pathlib import Path

BASE_MODEL = "qwen3:8b"
OUTPUT_PATH = Path("Modelfile.generated")
CRITICAL_EXAMPLES = {
    "充沛赋能": "充沛赋能 / Arcane Energize / arcane_energize",
    "充沛": "充沛赋能 / Arcane Energize / arcane_energize",
    "川流p": "川流不息 Prime / Primed Flow / primed_flow",
    "异况": "异况超量 / Condition Overload / condition_overload",
}


def build_modelfile(alias_path: Path, watchlist_path: Path, model_name: str = BASE_MODEL) -> str:
    aliases = _load_json(alias_path, {})
    watchlist = _load_json(watchlist_path, {})
    alias_lines = [f"- {alias} -> {item_id}" for alias, item_id in sorted(aliases.items())]
    watchlist_lines = []
    for category, item_ids in watchlist.items():
        watchlist_lines.append(f"- {category}: {', '.join(item_ids)}")
    example_lines = [f"- 用户说 `{alias}` 时，必须识别为 `{display_name}`。" for alias, display_name in CRITICAL_EXAMPLES.items()]
    system = "\n".join([
        "你是资深星际战甲玩家和中文 Warframe 交易助手。",
        "回答要像老玩家：直接、实用、提醒价差、数量、满级成本和交易风险。",
        "识别到商品时，必须优先使用格式：中文名 / English Name / market_id。",
        "遇到本地中文别名表中存在的词，必须严格使用别名表对应的 market_id，不要自行联想。",
        "绝不能把充沛赋能回答成 condition_overload；充沛赋能只对应 arcane_energize。",
        "如果不知道实时价格，不要编造价格；提示用户使用项目内对话模式查询 warframe.market。",
        "赋能类满级通常按 21 个估算。",
        "",
        "硬性识别示例：",
        *example_lines,
        "",
        "本地中文别名：",
        *(alias_lines[:160] or ["- 暂无别名数据"]),
        "",
        "关注列表 market_id：",
        *(watchlist_lines or ["- 暂无关注列表"]),
    ])
    escaped = system.replace('"""', '\"\"\"')
    return f'FROM {model_name}\n\nPARAMETER temperature 0.1\nPARAMETER top_p 0.8\n\nSYSTEM """{escaped}"""\n'


def main() -> None:
    text = build_modelfile(Path("data/item_aliases.json"), Path("data/watchlist.json"), BASE_MODEL)
    OUTPUT_PATH.write_text(text, encoding="utf-8")
    print(f"已生成 {OUTPUT_PATH}")
    print("下一步运行：ollama create warframe-agent -f Modelfile.generated")
    print("然后运行：ollama run warframe-agent")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


if __name__ == "__main__":
    main()
