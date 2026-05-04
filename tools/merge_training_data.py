"""合并真实对话日志与合成训练数据。"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def merge_training_data(
    min_rating: int = 3,
    output_path: Path = DATA_DIR / "training_data_merged.jsonl",
):
    all_examples = []

    # 真实对话日志
    real_path = DATA_DIR / "conversation_logs.jsonl"
    if real_path.exists():
        with real_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if entry.get("rating") and entry["rating"] < min_rating:
                    continue
                all_examples.append({
                    "messages": [
                        {"role": "system", "content": "你是资深星际战甲玩家和中文交易助手。"},
                        {"role": "user", "content": entry["user_message"]},
                        {"role": "assistant", "content": entry["assistant_reply"]},
                    ],
                    "source": "real",
                    "rating": entry.get("rating"),
                })

    # 合成数据
    synthetic_path = DATA_DIR / "training_data_synthetic.jsonl"
    if synthetic_path.exists():
        with synthetic_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                pair = json.loads(line)
                pair["source"] = "synthetic"
                all_examples.append(pair)

    # 去重
    seen = set()
    unique = []
    for ex in all_examples:
        user_msg = ex["messages"][1]["content"] if len(ex["messages"]) > 1 else ""
        if user_msg not in seen:
            seen.add(user_msg)
            unique.append(ex)

    with output_path.open("w", encoding="utf-8") as f:
        for ex in unique:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"Merged {len(unique)} unique examples -> {output_path}")


if __name__ == "__main__":
    merge_training_data()
