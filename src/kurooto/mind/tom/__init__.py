"""Theory of mind with provenance (Brain, 0.8.0 stage 14): an inspectable model of your mind, used only to be more
helpful and
quieter (level and timing), never more persuasive. Invariants I-13, I-14, I-7.

    model.py          rows {part, subject, claim, source, confidence, evidence}; Wrong and Forget; the deny-list; the
    purposes
    knowledge.py      mastery per concept by Bayesian knowledge tracing; explanation level; the study frontier
    beliefs_about.py  what you believe about your work and Kurooto's state; false-belief correction, once, with evidence
    goals.py          stated goals and hedged inferred intentions; the workspace's standing goals
    prefs.py          how you like help, with its source and date
    attention_of.py   what you're on now; only ever delays a message
    results.py        exam results you report: evidence, a line in exam prep, an offer of more preparation time
"""

from kurooto.core.config import register_defaults

PART = "tom"  # its switch: mind.tom.on

register_defaults(
    "mind",
    {
        "tom": {
            "on": True,  # a model of what you know, believe, want and prefer, each row with its source
            "false_beliefs": True,  # tell you once, with the evidence, when something you were told proved wrong
            "attention": False,  # hold a message while you're deep in something (needs the activity stream)
            "from_chat": True,  # an exam result you report ("I got 12/30 on the LA midterm") counts as evidence (0.9.0)
        }
    },
)
