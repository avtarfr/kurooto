"""Stands in for claude in tests (`claude -p --output-format json`). FAKE_CLI_MODE: ok | limit | auth | whoami.
FAKE_CLI_LIMIT_FOR: the accounts at their limit ("default" for the usual sign-in, else the CLAUDE_CONFIG_DIR folder's
name), comma-separated. whoami answers with the CLAUDE_CONFIG_DIR it was started with."""

import json
import os
import sys

mode = os.environ.get("FAKE_CLI_MODE", "ok")
config = os.environ.get("CLAUDE_CONFIG_DIR", "")
account = os.path.basename(config.rstrip("/\\")) if config else "default"
if account in os.environ.get("FAKE_CLI_LIMIT_FOR", "").split(","):
    mode = "limit"
prompt = sys.stdin.read()
if mode == "whoami":
    print(json.dumps({"type": "result", "is_error": False, "result": f"config dir: {config or '(none)'}"}))
elif mode == "ok":
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
