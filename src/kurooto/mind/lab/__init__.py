"""The research lab (Brain, 0.8.0 stage 11): overnight, pre-registered experiments on any project with a measurable
objective, in a sandbox, when the computer can spare it. The same pipeline, with gates, improves Kurooto itself
(mind/improve.py). Invariants I-6 and I-12.

    protocol.py   the lab protocol (objective, how to run, how to measure, what may change), drafted from a repo
    prereg.py     the batch is written down and its sha256 goes in the log before the first run   [protected]
    scoring.py    wins, replication, nulls; the score is the replication rate                      [protected]
    sandbox.py    no network, read-only system, limits; bubblewrap on Linux, sandbox-exec on macOS  [protected]
    runner.py     baseline, register, run, replicate the winners, analyse, propose; the night's batches
    report.py     the morning digest, /lab, the results

A winner arrives as a proposal; only you apply it. Null results are reported as prominently as wins.
"""

from kurooto.core.config import register_defaults

PART = "lab"  # its switch: mind.lab.on

register_defaults(
    "mind",
    {
        "lab": {
            "on": True,  # overnight pre-registered experiments on the projects you list (needs a sandbox: Linux, macOS)
            "projects": [],  # folders (or names of repository projects) the lab may run experiments on
            "gpu_hours_per_night": 2,  # the most it uses a night, in hours of run time
            "max_per_night": 40,  # the most configurations in a batch
            "run_wall_s": 1800,  # the longest one run may take, in seconds
            "seed": 0,  # a fixed seed for the sampled configurations (0: a new sample each day)
            "gpu": False,  # let runs see the GPU (off: CPU only)
            "in_repo": False,  # keep lab.toml in the project's .kurooto folder (off: in Kurooto's own state)
        },
        "improve": {
            "on": True
        },  # Kurooto improving itself through gated proposals; nothing changes without your say-so
    },
)
