"""LoRA 微调脚本 — 基于 unsloth 对 qwen3:8b 进行 QLoRA 微调。

依赖：
    pip install unsloth torch transformers datasets peft trl

GPU 要求：8GB+ VRAM

用法：
    python tools/finetune.py                          # 使用默认参数
    python tools/finetune.py --epochs 5 --lr 1e-4     # 自定义参数
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
TRAINING_DATA = DATA_DIR / "training_data_merged.jsonl"
OUTPUT_DIR = DATA_DIR / "finetuned"
BASE_MODEL = "unsloth/Qwen3-8b-bnb-4bit"


def load_training_data(path: Path) -> list[dict]:
    """加载 JSONL 训练数据。"""
    examples = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def format_chat(example: dict, tokenizer) -> str:
    """将 messages 格式转换为 tokenizer 的 chat 模板。"""
    messages = example.get("messages", [])
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )


def main():
    parser = argparse.ArgumentParser(description="LoRA 微调 qwen3:8b")
    parser.add_argument("--data", type=Path, default=TRAINING_DATA, help="训练数据路径")
    parser.add_argument("--output", type=Path, default=OUTPUT_DIR, help="输出目录")
    parser.add_argument("--epochs", type=int, default=3, help="训练轮数")
    parser.add_argument("--lr", type=float, default=2e-4, help="学习率")
    parser.add_argument("--batch", type=int, default=2, help="每设备 batch size")
    parser.add_argument("--grad-accum", type=int, default=4, help="梯度累积步数")
    parser.add_argument("--max-seq-len", type=int, default=2048, help="最大序列长度")
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32, help="LoRA alpha")
    args = parser.parse_args()

    if not args.data.exists():
        print(f"错误: 训练数据不存在 — {args.data}")
        print("请先运行: python tools/generate_training_data.py")
        print("         python tools/merge_training_data.py")
        sys.exit(1)

    # ── 1. 加载模型（4-bit 量化） ──
    print(f"加载基础模型: {BASE_MODEL}")
    from unsloth import FastLanguageModel

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=args.max_seq_len,
        dtype=None,  # 自动检测
        load_in_4bit=True,
    )

    # ── 2. 应用 LoRA ──
    print(f"应用 LoRA: r={args.lora_r}, alpha={args.lora_alpha}")
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    # ── 3. 加载并格式化训练数据 ──
    print(f"加载训练数据: {args.data}")
    raw_examples = load_training_data(args.data)
    print(f"  共 {len(raw_examples)} 条训练样本")

    from datasets import Dataset

    formatted = [format_chat(ex, tokenizer) for ex in raw_examples]
    dataset = Dataset.from_dict({"text": formatted})

    # ── 4. SFT 训练 ──
    from trl import SFTTrainer
    from transformers import TrainingArguments

    training_args = TrainingArguments(
        output_dir=str(args.output / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        gradient_accumulation_steps=args.grad_accum,
        learning_rate=args.lr,
        fp16=True,
        logging_steps=10,
        save_strategy="epoch",
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        optim="adamw_8bit",
        seed=42,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=training_args,
        dataset_text_field="text",
        max_seq_length=args.max_seq_len,
        packing=True,
    )

    print("开始训练...")
    trainer.train()

    # ── 5. 保存 LoRA adapter ──
    adapter_dir = args.output / "adapter"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(adapter_dir))
    tokenizer.save_pretrained(str(adapter_dir))
    print(f"LoRA adapter 已保存到: {adapter_dir}")

    # 保存训练元信息
    meta = {
        "base_model": BASE_MODEL,
        "lora_r": args.lora_r,
        "lora_alpha": args.lora_alpha,
        "epochs": args.epochs,
        "learning_rate": args.lr,
        "training_samples": len(raw_examples),
        "max_seq_len": args.max_seq_len,
    }
    (args.output / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    print(f"训练元信息已保存到: {args.output / 'meta.json'}")
    print("\n下一步: python tools/rebuild_ollama_model.py")


if __name__ == "__main__":
    main()
