# Add-ons to publish

Each folder here is a Kurooto add-on that's ready to become a repository of its own: copy the folder's contents to
the new repository's top, tag a release (`v1.0.0`), and anyone can add it with
`kurooto addons add <its git address> --ref v1.0.0` (docs/wiki/user/add-ons.md#add-ons-by-link).

| Folder | Feature | What it does | Starts |
|---|---|---|---|
| `restic-backups/` | Machine backups (restic) | backs up your folders with restic, thins out and checks | restic |
| `desktop-helpers/` | Desktop helpers | rings the phone (KDE Connect) and wakes the screen at the alarm; pings | kdeconnect-cli, hyprctl, swaymsg, xset |
| `habits/` | Your command words | your own short words for commands and requests (`/j` for `/journal`) | nothing |
| `handwriting-pull/` | Handwriting from the cloud | copies new handwritten pages from a cloud folder with rclone | rclone, nmcli |

Every one has its manifest (`kurooto-addon.json`, the card you agree to), a README and tests. They run inside Kurooto
with a pretend home: `uv run pytest addons/` here (`conftest.py` adds each one by link, as a user would), and
`tests/unit/test_addon_packages.py` checks that each loads with exactly what its card says. None of them reaches a
host on the internet itself; the programs they start are named on their cards.

How to write one: docs/wiki/dev/modules.md, "Add-ons by link".
