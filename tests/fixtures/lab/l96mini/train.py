"""A tiny Lorenz-96-style stand-in: 'trains' a closure with a learning rate and width, writes metrics.json."""

import argparse
import json
import math
import pathlib

ap = argparse.ArgumentParser()
ap.add_argument("--config", required=True)
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()
cfg = json.loads(pathlib.Path(a.config).read_text())
lr, width = float(cfg["lr"]), int(cfg["width"])
# a smooth bowl with its minimum near lr=3e-3, width=128, plus a little seed noise
rmse = 0.5 + (math.log10(lr) + 2.5) ** 2 * 0.2 + (math.log2(width) - 7) ** 2 * 0.02 + ((a.seed * 7919) % 13) * 1e-4
pathlib.Path("metrics.json").write_text(json.dumps({"val_rmse": round(rmse, 5)}))
