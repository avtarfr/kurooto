"""Who's on the other end of a connection to the dashboard. On a computer several people sign in to (a shared Linux
machine), another account could reach 127.0.0.1 too and read the key from the page it serves; so on Linux every API
request must come from this user account, and is refused when that can't be told."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def peer_uid(client_port: int, server_port: int, proc_net: str = "/proc/net") -> int | None:
    """Linux: the user account that owns the connection coming from client_port to our server_port, read from the
    kernel's socket table. None if it can't be found."""
    for name in ("tcp", "tcp6"):
        try:
            rows = Path(proc_net, name).read_text(encoding="ascii", errors="replace").splitlines()[1:]
        except OSError:
            continue
        for row in rows:
            f = row.split()
            if len(f) < 8:
                continue
            try:
                lport = int(f[1].rsplit(":", 1)[1], 16)
                rport = int(f[2].rsplit(":", 1)[1], 16)
            except (IndexError, ValueError):
                continue
            if lport == client_port and rport == server_port:
                try:
                    return int(f[7])
                except ValueError:
                    return None
    return None


def same_user(client_address, server_port: int, platform: str | None = None, proc_net: str = "/proc/net") -> bool:
    """May this connection use the dashboard's API? On Linux only if it comes from this user account, read from the
    kernel's socket table (refused when that can't be told). Elsewhere the dashboard's own protections apply: it only
    listens on 127.0.0.1, and every request needs the key only its own page gets."""
    if (platform or sys.platform) != "linux":
        return True
    try:
        uid = peer_uid(int(client_address[1]), int(server_port), proc_net)
    except (TypeError, ValueError, IndexError):
        return False
    # root may: it can already read everything this account owns (and relays such as WSL's localhost forwarder run as
    # root)
    return uid is not None and uid in (os.getuid(), 0)
