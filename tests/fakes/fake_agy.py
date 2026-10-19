"""Stands in for agy in tests. FAKE_AGY_MODE: ok | prompt | denied | limit | auth | silent | slow | crash."""

import os
import sys
import time

mode = os.environ.get("FAKE_AGY_MODE", "ok")
prompt = sys.argv[sys.argv.index("-p") + 1] if "-p" in sys.argv else ""
model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else ""
if mode == "ok":
    print(f"answer from {model}: {prompt.splitlines()[-1][:60]}")
elif mode == "prompt":  # what it was asked, in full
    print(prompt)
elif mode == "denied":
    print("no output produced")
elif mode == "limit":
    print("Error: RESOURCE_EXHAUSTED: quota exceeded", file=sys.stderr)
    sys.exit(1)
elif mode == "auth":
    print("Please sign in: not logged in", file=sys.stderr)
    sys.exit(1)
elif mode == "signed-out":  # what agy really prints when nobody has signed in (CI probe, 2026-10-19)
    print("Authentication required. Please visit the URL to log in:\n  https://accounts.google.com/o/oauth2/auth?x=y")
    sys.exit(1)
elif mode == "silent":
    pass
elif mode == "slow":
    time.sleep(60)
elif mode == "crash":
    print("Traceback: something broke", file=sys.stderr)
    sys.exit(2)
