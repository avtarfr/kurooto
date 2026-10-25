"""Skills it learns (Brain, 0.8.0 stage 12): a library of tested skills made from tasks that worked out and, if you turn
it on, from what you do over and over, and a weekly local fine-tune on examples whose outcome was checked. Invariant
I-11.

    library.py   the skills: folders, regression gate, always-ask start, variants, retirement        [protected]
    distill.py   a candidate from an applied proposal that held for 48 hours and passed its checks
    demos.py     a candidate from a sequence you repeat (opt-in), offered once as a question
    finetune.py  the weekly QLoRA from the base weights, verified forgetting, the adapter as a challenger  [protected]
    qlora.py     the trainer the fine-tune calls in a subprocess (needs torch, transformers, peft, bitsandbytes)
"""
