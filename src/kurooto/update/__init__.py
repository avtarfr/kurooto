"""Updates: signed releases, installed side by side, switched atomically, rolled back if the new one won't run.

Layout (in the app folder):
    launcher.py            stdlib only; what autostart runs. Starts the current version and rolls back on a
                           crash loop during a new version's probation.
    current.json           {"version": "0.2.0"}  (written atomically)
    previous.json          the version before, for rollback
    update.json            {"phase": "trial" | "ok", "from": ..., "to": ..., "since": ...}
    versions/<v>/          that version's files and its own .venv
    bad.json               versions that failed probation (never retried automatically)

Where updates come from: a channel pointer (stable.json or beta.json) on GitHub Pages, signed with ed25519.
The pointer names a release whose manifest.json (also signed) lists every file with its sha256.
"""
