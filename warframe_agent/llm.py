from __future__ import annotations

from . import config
from .dictionary import normalize_market_id


def resolve_with_ollama(name: str, model: str = config.MODEL_NAME) -> str | None:
    try:
        import ollama
    except ImportError as exc:
        raise RuntimeError("Ollama Python package is not installed") from exc

    prompt = (
        "你是 Warframe 和 warframe.market 物品 URL 专家。"
        "把用户输入的中文或英文物品名转换成 warframe.market item url_name。"
        "只输出小写英文 url_name，不要解释，不要 Markdown。"
        "例如：充沛赋能 -> arcane_energize；川流不息 Prime -> primed_flow。"
        f"用户输入：{name}"
    )
    response = ollama.generate(model=model, prompt=prompt)
    text = response.get("response", "").strip().splitlines()[0]
    item_id = normalize_market_id(text)
    return item_id or None
