"""Stands in for codex or claude in tests. FAKE_CLI_MODE: ok | limit | auth | json-error."""

import json
import os
import sys

mode = os.environ.get("FAKE_CLI_MODE", "ok")
prompt = sys.stdin.read()
args = sys.argv[1:]
if "exec" in args:  # codex
    if mode == "ok":
        out = args[args.index("--output-last-message") + 1]
        open(out, "w").write(f"codex says: {prompt.strip().splitlines()[-1]}")
    elif mode == "limit":
        print("ERROR: You've hit your usage limit", file=sys.stderr)
        sys.exit(1)
    elif mode == "auth":
        print("Not logged in. Run codex login", file=sys.stderr)
        sys.exit(1)
else:  # claude -p --output-format json
    if mode == "ok":
        print(
            json.dumps(
                {"type": "result", "subtype": "success", "is_error": False, "result": f"claude says: {prompt.strip()}"}
            )
        )
    elif mode == "auth":
        print(
            json.dumps(
                {
                    "type": "result",
                    "subtype": "error",
                    "is_error": True,
                    "result": "Invalid API key · Please run /login",
                }
            )
        )
        sys.exit(1)
    elif mode == "limit":
        print(json.dumps({"type": "result", "is_error": True, "result": "Claude usage limit reached"}))
        sys.exit(1)
