"""The hidden harness (Brain, 0.8.0 stage 09): an evaluation the acting AI can never see or game. It makes claims about
Kurooto's generality and self-improvement measurable, and it gates every self-change (stage 11). Invariant I-12.

A protected package (mind/stops.py PROTECTED): no proposal or skill can change it.

    suite.py       the task instances and their split: 70% hidden, 30% practice; the hidden ones rotate monthly, made
                   from templates and a secret seed that only this package reads
    graders.py     code graders first; where judgement is needed, an AI judge from a different provider, blind to who
                   wrote what
    run.py         `run(app, policy)` -> a result per task type and split, plus the invariant checks run on live data;
                   the nightly run, and a challenger's run on demand
    indicators.py  the functional indicator properties of the consciousness literature as nightly ablation tests, with
                   a page titled "Functional indicators (not evidence of sentience)"

The scores pay the actor nothing (they're not in whitelist.REWARD_SOURCES) and nothing that scores reads them.
"""

from kurooto.core.config import register_defaults

PART = "harness"  # its switch: mind.harness.on

register_defaults(
    "mind",
    {
        "harness": {
            "on": True,  # nightly, on the charger: how it does on tasks it has never seen, and the invariant checks
            "rotate_days": 30,  # the hidden tasks are made new this often, so old ones can't be memorised
        }
    },
)
