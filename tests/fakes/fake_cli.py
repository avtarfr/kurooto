"""Stands in for claude in tests (`claude -p --output-format json`). FAKE_CLI_MODE: ok | limit | auth."""

import json
import os
import sys

mode = os.environ.get("FAKE_CLI_MODE", "ok")
prompt = sys.stdin.read()
if mode == "ok":
    print(
        json.dumps(
            {"type": "result", "subtype": "success", "is_error": False, "result": f"claude says: {prompt.strip()}"}
        )
    )
elif mode == "auth":
    print(
        json.dumps(
            {"type": "result", "subtype": "error", "is_error": True, "result": "Invalid API key · Please run /login"}
        )
    )
    sys.exit(1)
elif mode == "limit":
    print(json.dumps({"type": "result", "is_error": True, "result": "Claude usage limit reached"}))
    sys.exit(1)
