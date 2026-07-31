"""C1 LoRA training — one arm per invocation, identical config across arms.

Usage:  .venv-train/bin/python experiments/c1_train.py --arm validated|suggested

Deliberately plain: full-sequence LM loss over chat-templated rows, the
same recipe for both arms, so the ONLY difference between adapters is
which rows went in (replay-validated vs unvalidated proposals,
matched token budgets).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

os.environ.setdefault("HF_HOME", "/home/jovyan/buckets/hf_cache")

import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

BASE = "Qwen/Qwen2.5-7B-Instruct"
DATA = Path("experiments/c1_data")
OUT = Path("experiments/c1_adapters")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=["validated", "suggested"], required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=1e-4)
    args = parser.parse_args()

    rows = [json.loads(l) for l in (DATA / f"c1_train_{args.arm}.jsonl").open()]
    tokenizer = AutoTokenizer.from_pretrained(BASE)

    def encode(row):
        text = tokenizer.apply_chat_template(row["messages"], tokenize=False,
                                             add_generation_prompt=False)
        ids = tokenizer(text, truncation=True, max_length=1536)
        return {"input_ids": ids["input_ids"], "attention_mask": ids["attention_mask"]}

    dataset = Dataset.from_list([encode(r) for r in rows])
    model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16,
                                                 device_map={"": 0})
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    ))
    model.enable_input_require_grads()  # needed for PEFT + checkpointing
    model.print_trainable_parameters()

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=str(OUT / f"{args.arm}-ckpt"),
            num_train_epochs=args.epochs,
            per_device_train_batch_size=1,
            gradient_accumulation_steps=8,
            gradient_checkpointing=True,
            learning_rate=args.lr,
            bf16=True,
            logging_steps=5,
            save_strategy="no",
            report_to=[],
            seed=0,
        ),
        train_dataset=dataset,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )
    result = trainer.train()
    adapter_dir = OUT / args.arm
    model.save_pretrained(str(adapter_dir))
    print(json.dumps({"arm": args.arm, "rows": len(rows),
                      "train_loss": round(result.training_loss, 4),
                      "adapter": str(adapter_dir)}))


if __name__ == "__main__":
    main()
