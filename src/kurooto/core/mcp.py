"""`kurooto mcp`: Kurooto's tools for agent programs (agy, Codex, Claude Code, or any other MCP client), over the
Model Context Protocol: JSON-RPC 2.0 messages, one per line, on stdin and stdout.

It is only a bridge. Every tool call goes to the Kurooto running on this computer, through its local page
(127.0.0.1) with a key that is good for the tools and nothing else, so a tool does exactly what it does on calls
and in API requests, with the features you have on. When Kurooto isn't running, the tools are the ones it last
listed, and calling one says that Kurooto isn't running.

Standard library only, and quick to start: agent programs start it for every run.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

from kurooto import __version__
from kurooto.core.paths import Paths, paths
from kurooto.core.state import jload

NAME = "kurooto"
PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")  # newest first
ENV_URL, ENV_TOKEN = "KUROOTO_TOOLS_URL", "KUROOTO_TOOLS_TOKEN"
# what paths() reads, so the bridge finds Kurooto's folders even when an agent program passes it a short environment
ENV_PATHS = ("KUROOTO_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "LOCALAPPDATA")
NOT_RUNNING = (
    "Kurooto isn't running on this computer right now, so this wasn't done. Tell the user; they can start it "
    "with `kurooto on`."
)
INSTRUCTIONS = (
    "Kurooto is the user's personal assistant on this computer. These tools act for them: reminders, calls, "
    "deadlines, notes and more, depending on the features they turned on. Notes they wrote are theirs: add to "
    "them or create new ones, never reword or remove their text. Only say you did something if the tool's answer "
    "says it was done."
)


def access_file(p: Paths | None = None) -> Path:
    """Where the running Kurooto leaves its address and the tools-only key (owner-only; new at every start)."""
    return (p or paths()).state / "tools-access.json"


def tools_cache(p: Paths | None = None) -> Path:
    return (p or paths()).state / "tools-list.json"


def _console(python: str) -> str:
    """pythonw.exe has no stdin/stdout on Windows: use python.exe next to it."""
    exe = Path(python)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").exists():
        return str(exe.parent / "python.exe")
    return str(exe)


def command(persistent: bool = False) -> list[str]:
    """How an agent program starts `kurooto mcp`. persistent=True is for a setting saved inside the agent program
    (agy), which must keep working after Kurooto updates itself: it goes through the installed launcher if any."""
    if persistent:
        p = paths()
        python = (jload(p.app / "install.json", {}) or {}).get("python")
        if python and (p.app / "launcher.py").is_file():
            return [_console(python), str(p.app / "launcher.py"), "cli", "mcp"]
    return [_console(sys.executable), "-m", "kurooto", "mcp"]


def path_env() -> dict:
    return {k: os.environ[k] for k in ENV_PATHS if os.environ.get(k)}


def run_env(p: Paths) -> dict:
    """What an agent run passes to `kurooto mcp`: Kurooto's folders and, if it's running, its address and key."""
    out = path_env()
    a = jload(access_file(p), {}) or {}
    if a.get("url") and a.get("token"):
        out[ENV_URL], out[ENV_TOKEN] = a["url"], a["token"]
    return out


class Bridge:
    """Requests to the running Kurooto. None when it isn't running (or doesn't answer)."""

    def __init__(self, timeout: float = 300):
        self.timeout = timeout

    def _targets(self) -> list[tuple[str, str]]:
        out = []
        if os.environ.get(ENV_URL) and os.environ.get(ENV_TOKEN):
            out.append((os.environ[ENV_URL], os.environ[ENV_TOKEN]))
        a = jload(access_file(), {}) or {}
        if a.get("url") and a.get("token") and (a["url"], a["token"]) not in out:
            out.append((a["url"], a["token"]))  # Kurooto restarted since this run began: its new key
        return out

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict] | None:
        got = None
        for url, token in self._targets():
            req = urllib.request.Request(  # noqa: S310 (Kurooto's own 127.0.0.1 page)
                url.rstrip("/") + "/api/" + path,
                data=None if body is None else json.dumps(body).encode(),
                method=method,
                headers={"X-Kurooto-Tools": token, "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:  # noqa: S310
                    return r.status, json.loads(r.read() or b"{}")
            except urllib.error.HTTPError as e:
                try:
                    got = e.code, json.loads(e.read() or b"{}")
                except ValueError:
                    got = e.code, {}
                if e.code not in (401, 403):
                    return got
            except (OSError, ValueError):
                continue
        return got


class RpcError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _text(text: str, error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": error}


class Server:
    def __init__(self, bridge: Bridge, out):
        self.bridge = bridge
        self.out = out
        self._write_lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    # ------------------------------------------------------------------------------------- the protocol
    def initialize(self, params: dict) -> dict:
        asked = params.get("protocolVersion")
        return {
            "protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": NAME, "title": "Kurooto", "version": __version__},
            "instructions": INSTRUCTIONS,
        }

    def list_tools(self) -> dict:
        r = self.bridge.request("GET", "tools")
        tools = r[1].get("tools") if r and r[0] == 200 else None
        if not isinstance(tools, list):
            tools = jload(tools_cache(), []) or []  # not running: what it last listed
        return {
            "tools": [
                {
                    "name": t["name"],
                    "description": str(t.get("description") or ""),
                    "inputSchema": t.get("schema") or {"type": "object", "properties": {}},
                }
                for t in tools
                if isinstance(t, dict) and t.get("name")
            ]
        }

    def call_tool(self, params: dict) -> dict:
        name, args = params.get("name"), params.get("arguments")
        if not isinstance(name, str) or not name:
            raise RpcError(-32602, "tools/call needs the tool's name")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return _text("The arguments must be a JSON object.", error=True)
        r = self.bridge.request("POST", "tools/call", {"name": name, "args": args, "via": "mcp"})
        if r is None:
            return _text(NOT_RUNNING, error=True)
        code, body = r
        if code == 404:
            raise RpcError(-32602, f"Unknown tool: {name}")
        if code != 200:
            return _text(str(body.get("error") or f"Kurooto answered HTTP {code}."), error=True)
        res = body.get("result")
        text = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False, indent=1, default=str)
        return _text(text, error=not body.get("ok", True))

    def dispatch(self, method: str, params: dict):
        if method == "initialize":
            return self.initialize(params)
        if method == "ping":
            return {}
        if method == "tools/list":
            return self.list_tools()
        if method == "tools/call":
            return self.call_tool(params)
        raise RpcError(-32601, f"Method not found: {method}")

    def handle(self, msg) -> dict | None:
        """One message in, its response out (None for a notification or a stray response)."""
        if not isinstance(msg, dict):
            return _error(None, -32600, "Invalid Request")
        if "method" not in msg and ("result" in msg or "error" in msg):
            return None  # a response to a request of ours; we send none
        mid, method, params = msg.get("id"), msg.get("method"), msg.get("params")
        bad_id = "id" in msg and not (mid is None or isinstance(mid, (str, int)) and not isinstance(mid, bool))
        if msg.get("jsonrpc") != "2.0" or not isinstance(method, str) or bad_id:
            return _error(mid if not bad_id else None, -32600, "Invalid Request")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            return None if "id" not in msg else _error(mid, -32602, "params must be an object")
        if "id" not in msg:  # a notification: notifications/initialized, notifications/cancelled, ...
            return None
        try:
            return {"jsonrpc": "2.0", "id": mid, "result": self.dispatch(method, params)}
        except RpcError as e:
            return _error(mid, e.code, e.message)
        except Exception as e:
            return _error(mid, -32603, f"Internal error: {type(e).__name__}: {e}"[:300])

    # ---------------------------------------------------------------------------------------- the pipe
    def send(self, obj) -> None:
        data = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self._write_lock:
            self.out.write(data)
            self.out.flush()

    def feed(self, line: bytes | str) -> None:
        """One line from the client. Tool calls run alongside, so a ping or a second call isn't kept waiting."""
        try:
            msg = json.loads(line)
        except ValueError:
            self.send(_error(None, -32700, "Parse error"))
            return
        if isinstance(msg, list):  # a batch (older protocol versions)
            if not msg:
                self.send(_error(None, -32600, "Invalid Request"))
                return
            self._spawn(lambda: self._batch(msg))
        elif isinstance(msg, dict) and msg.get("method") == "tools/call":
            self._spawn(lambda: self._reply(msg))
        else:
            self._reply(msg)

    def _reply(self, msg) -> None:
        out = self.handle(msg)
        if out is not None:
            self.send(out)

    def _batch(self, msgs: list) -> None:
        outs = [o for o in (self.handle(m) for m in msgs) if o is not None]
        if outs:
            self.send(outs)

    def _spawn(self, fn) -> None:
        self._threads = [t for t in self._threads if t.is_alive()]
        t = threading.Thread(target=fn, name="mcp-call", daemon=True)
        self._threads.append(t)
        t.start()

    def wait(self, seconds: float) -> None:
        for t in list(self._threads):
            t.join(seconds)


def _error(mid, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def serve(stdin=None, stdout=None, bridge: Bridge | None = None) -> int:
    """Run until the client closes stdin."""
    srv = Server(bridge or Bridge(), stdout or sys.stdout.buffer)
    try:
        for raw in stdin or sys.stdin.buffer:
            line = raw.strip()
            if line:
                srv.feed(line)
    except KeyboardInterrupt:
        pass
    srv.wait(30)  # answers to calls still running
    return 0
