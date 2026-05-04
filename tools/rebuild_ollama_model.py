"""合并 LoRA adapter 到基础模型，导出 GGUF 并创建 Ollama 模型。

依赖：
    pip install unsloth torch transformers peft

用法：
    python tools/rebuild_ollama_model.py
    python tools/rebuild_ollama_model.py --model-name warframe-agent-v2
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
FINETUNED_DIR = DATA_DIR / "finetuned"
ADAPTER_DIR = FINETUNED_DIR / "adapter"
BASE_MODEL = "unsloth/Qwen3-8b-bnb-4bit"
DEFAULT_MODEL_NAME = "warframe-agent-v2"


def load_meta() -> dict:
    meta_path = FINETUNED_DIR / "meta.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding="utf-8"))
    return {}


def build_system_prompt() -> str:
    """复用 build_ollama_model.py 的逻辑构建 system prompt。"""
    try:
        # 同目录下导入
        sys.path.insert(0, str(Path(__file__).parent))
        from build_ollama_model import build_modelfile
        alias_path = Path("data/item_aliases.json")
        watchlist_path = Path("data/watchlist.json")
        modelfile_text = build_modelfile(alias_path, watchlist_path, "placeholder")
        start = modelfile_text.find('SYSTEM """')
        if start == -1:
            return "你是资深星际战甲玩家和中文 Warframe 交易助手。"
        start += len('SYSTEM """')
        end = modelfile_text.find('"""', start)
        return modelfile_text[start:end].strip()
    except Exception:
        return "你是资深星际战甲玩家和中文 Warframe 交易助手。"


def main():
    parser = argparse.ArgumentParser(description="合并 LoRA 并创建 Ollama 模型")
    parser.add_argument("--model-name", default=DEFAULT_MODEL_NAME, help="Ollama 模型名")
    parser.add_argument("--base-model", default=BASE_MODEL, help="基础模型名")
    parser.add_argument("--quant", default="q4_k_m", help="GGUF 量化格式 (q4_k_m / q5_k_m / q8_0)")
    parser.add_argument("--skip-merge", action="store_true", help="跳过合并，直接用已有 GGUF")
    args = parser.parse_args()

    if not ADAPTER_DIR.exists() and not args.skip_merge:
        print(f"错误: LoRA adapter 目录不存在 — {ADAPTER_DIR}")
        print("请先运行: python tools/finetune.py")
        sys.exit(1)

    gguf_path = FINETUNED_DIR / f"{args.model_name}.gguf"
    modelfile_path = FINETUNED_DIR / "Modelfile.finetuned"

    # ── 1. 合并 LoRA 到基础模型 ──
    if not args.skip_merge:
        print(f"合并 LoRA adapter 到基础模型...")
        from unsloth import FastLanguageModel
        from peft import PeftModel

        # 加载基础模型（全精度用于合并）
        base_model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=args.base_model,
            max_seq_length=2048,
            dtype=None,
            load_in_4bit=False,  # 全精度合并
        )

        # 加载 LoRA adapter
        model = PeftModel.from_pretrained(base_model, str(ADAPTER_DIR))

        # 合并权重
        print("合并权重中...")
        merged = model.merge_and_unload()

        # 保存合并后的完整模型
        merged_dir = FINETUNED_DIR / "merged"
        merged_dir.mkdir(parents=True, exist_ok=True)
        merged.save_pretrained(str(merged_dir))
        tokenizer.save_pretrained(str(merged_dir))
        print(f"合并模型已保存到: {merged_dir}")

        # ── 2. 导出 GGUF ──
        print(f"导出 GGUF ({args.quant})...")
        from unsloth import FastLanguageModel as FLM

        # 用 unsloth 的 save 方法直接导出 gguf
        gguf_path_str = str(gguf_path)
        merged.save_pretrained_gguf(
            gguf_path_str,
            tokenizer,
            quantization_method=args.quant,
        )
        print(f"GGUF 已导出: {gguf_path}")
    else:
        if not gguf_path.exists():
            print(f"错误: GGUF 文件不存在 — {gguf_path}")
            sys.exit(1)
        print(f"使用已有 GGUF: {gguf_path}")

    # ── 3. 生成 Modelfile ──
    print("生成 Modelfile...")
    system_prompt = build_system_prompt()
    escaped = system_prompt.replace('"""', '\\"\\"\\"')
    modelfile_content = (
        f"FROM {gguf_path}\n\n"
        f"PARAMETER temperature 0.1\n"
        f"PARAMETER top_p 0.8\n\n"
        f'SYSTEM """{escaped}"""\n'
    )
    modelfile_path.write_text(modelfile_content, encoding="utf-8")
    print(f"Modelfile 已生成: {modelfile_path}")

    # ── 4. 创建 Ollama 模型 ──
    print(f"创建 Ollama 模型: {args.model_name}")
    result = subprocess.run(
        ["ollama", "create", args.model_name, "-f", str(modelfile_path)],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"Ollama 模型 '{args.model_name}' 创建成功！")
        print(f"测试: ollama run {args.model_name}")
    else:
        print(f"创建失败: {result.stderr}")
        print(f"你可以手动运行: ollama create {args.model_name} -f {modelfile_path}")
        sys.exit(1)

    # 保存构建信息
    meta = load_meta()
    meta["ollama_model"] = args.model_name
    meta["gguf_path"] = str(gguf_path)
    meta["quantization"] = args.quant
    (FINETUNED_DIR / "build_info.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False)
    )
    print("完成！")


if __name__ == "__main__":
    main()
