"""Stands in for an agent program (codex, claude or agy) in tests of Kurooto's MCP wiring.

It records how it was started (FAKE_AGENT_LOG: argv, its MCP server settings, the tools environment), then does
what the real program would: starts the MCP server it was given, initializes it and calls one tool
(FAKE_AGENT_TOOL with the JSON arguments FAKE_AGENT_ARGS), and answers with the tool's text.

    codex exec ... -c mcp_servers.kurooto.command=... --output-last-message FILE -   (prompt on stdin)
    claude -p --output-format json --mcp-config FILE ...                          (prompt on stdin)
    agy mcp add [--env K=V] kurooto -- COMMAND...                                 (setup: just recorded)
"""

import json
import os
import subprocess
import sys

argv = sys.argv[1:]
log = {"argv": argv, "tools_env": {k: v for k, v in os.environ.items() if k.startswith("KUROOTO_TOOLS_")}}


def save():
    if os.environ.get("FAKE_AGENT_LOG"):
        with open(os.environ["FAKE_AGENT_LOG"], "a", encoding="utf-8") as f:
            f.write(json.dumps(log) + "\n")


def use_tool(command, env):
    base = {k: os.environ[k] for k in ("PATH", "SYSTEMROOT", "HOME", "USERPROFILE", "TEMP", "TMP") if k in os.environ}
    p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, env={**base, **env})

    def ask(obj):
        p.stdin.write((json.dumps(obj) + "\n").encode())
        p.stdin.flush()
        return json.loads(p.stdout.readline()) if "id" in obj else None

    ask({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
    ask({"jsonrpc": "2.0", "method": "notifications/initialized"})
    args = json.loads(os.environ.get("FAKE_AGENT_ARGS") or "{}")
    name = os.environ.get("FAKE_AGENT_TOOL", "list_notes")
    r = ask({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": args}})
    p.stdin.close()
    p.wait(30)
    return r["result"]["content"][0]["text"]


if argv[:2] == ["mcp", "add"]:  # agy at setup
    save()
    sys.exit(int(os.environ.get("FAKE_AGENT_EXIT", "0")))

prompt = sys.stdin.read() if not sys.stdin.isatty() else ""
if "exec" in argv:  # codex
    over = dict(argv[i + 1].split("=", 1) for i, a in enumerate(argv) if a == "-c")
    log["config"] = over
    server = {k.split(".")[-1]: json.loads(v) for k, v in over.items() if k.startswith("mcp_servers.kurooto.")}
    save()
    text = use_tool([server["command"], *server["args"]], {k: os.environ[k] for k in server.get("env_vars", [])})
    with open(argv[argv.index("--output-last-message") + 1], "w", encoding="utf-8") as f:
        f.write(text)
elif "--mcp-config" in argv:  # claude
    with open(argv[argv.index("--mcp-config") + 1], encoding="utf-8") as f:
        cfg = json.load(f)
    log["config"] = cfg
    if "--settings" in argv:
        with open(argv[argv.index("--settings") + 1], encoding="utf-8") as f:
            log["settings"] = json.load(f)
    save()
    s = cfg["mcpServers"]["kurooto"]
    text = use_tool([s["command"], *s["args"]], s.get("env") or {})
    print(json.dumps({"type": "result", "is_error": False, "result": text}))
else:
    save()
    print("no tools given")
