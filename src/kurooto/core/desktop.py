"""A desktop notification on Windows, macOS or Linux. Best effort: if the OS refuses, nothing breaks.
Text goes in as program arguments or environment variables, never pasted into script source, so quotes can't
break out. The Windows script itself goes in as -EncodedCommand (base64 UTF-16), so its own quotes survive too."""

from __future__ import annotations

import base64
import os
import shutil
import sys

from kurooto.core import proc

_WIN_TOAST = r"""
$ErrorActionPreference = 'Stop'
$title = $env:KUROOTO_TITLE; $body = $env:KUROOTO_TEXT
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text></text><text></text></binding></visual></toast>')
$t = $xml.GetElementsByTagName('text')
$t.Item(0).AppendChild($xml.CreateTextNode($title)) | Out-Null
$t.Item(1).AppendChild($xml.CreateTextNode($body)) | Out-Null
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show(
  [Windows.UI.Notifications.ToastNotification]::new($xml))
"""

_MAC = "on run argv\ndisplay notification (item 2 of argv) with title (item 1 of argv)\nend run"


def notify(title: str, text: str, urgent: bool = False) -> bool:
    title, text = str(title)[:120], str(text)[:500]
    try:
        if sys.platform == "win32":
            script = base64.b64encode(_WIN_TOAST.encode("utf-16-le")).decode()
            env = {**os.environ, "KUROOTO_TITLE": title, "KUROOTO_TEXT": text}
            r = proc.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", script], timeout=20, env=env
            )
        elif sys.platform == "darwin":
            r = proc.run(["osascript", "-e", _MAC, title, text], timeout=10)
        elif shutil.which("notify-send"):
            r = proc.run(
                ["notify-send", "-a", "Kurooto", "-u", "critical" if urgent else "normal", title, text], timeout=10
            )
        else:
            return False
        return r.ok
    except Exception:
        return False
