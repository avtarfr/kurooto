"""The QLoRA trainer and generator the weekly fine-tune calls in a subprocess (mind/skills/finetune.py).

    python -m kurooto.mind.skills.qlora train    --base <hf name> --data train.jsonl --out <adapter dir>
    python -m kurooto.mind.skills.qlora generate --base <hf name> --adapter <adapter dir> --prompt "..."

It trains from the base weights every time (there is no argument for an earlier adapter), a small rank, one pass, 4-bit
base. Needs torch, transformers, peft and bitsandbytes and a CUDA card; nothing imports it unless the fine-tune runs.
NOT RUN ON THE BUILD MACHINE (no training packages there): the fake trainer in the tests covers the pipeline around it.
"""

from __future__ import annotations

import argparse
import json
import sys


def _load(base: str):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_quant_type="nf4")
    tok = AutoTokenizer.from_pretrained(base)
    model = AutoModelForCausalLM.from_pretrained(base, quantization_config=q, device_map="auto")
    return tok, model


def train(base: str, data: str, out: str) -> int:
    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    tok, model = _load(base)
    model = get_peft_model(
        prepare_model_for_kbit_training(model),
        LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05, task_type="CAUSAL_LM", target_modules="all-linear"),
    )
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)
    rows = [json.loads(line) for line in open(data, encoding="utf-8") if line.strip()]
    model.train()
    for r in rows:
        ids = tok(r["prompt"] + "\n" + r["completion"], return_tensors="pt", truncation=True, max_length=1024).to(
            model.device
        )
        loss = model(**ids, labels=ids["input_ids"]).loss
        loss.backward()
        opt.step()
        opt.zero_grad()
    model.save_pretrained(out)
    return 0


def generate(base: str, adapter: str, prompt: str) -> int:
    from peft import PeftModel

    tok, model = _load(base)
    model = PeftModel.from_pretrained(model, adapter)
    ids = tok(prompt, return_tensors="pt").to(model.device)
    out = model.generate(**ids, max_new_tokens=64, do_sample=False)
    sys.stdout.write(tok.decode(out[0][ids["input_ids"].shape[1] :], skip_special_tokens=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["train", "generate"])
    ap.add_argument("--base", required=True)
    ap.add_argument("--data")
    ap.add_argument("--out")
    ap.add_argument("--adapter")
    ap.add_argument("--prompt")
    a = ap.parse_args(argv)
    if a.mode == "train":
        return train(a.base, a.data, a.out)
    return generate(a.base, a.adapter, a.prompt or "")


if __name__ == "__main__":
    sys.exit(main())
