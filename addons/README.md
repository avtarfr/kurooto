# Add-ons, published

Each folder here is the source of a Kurooto add-on that's published as a public repository of its own (the folder's
contents, plus LICENSE, .gitignore and .github/CODEOWNERS), tagged `v1.0.0`. Kurooto lists them as **official
add-ons** (`src/kurooto/data/official_addons.json`, core/official.py), each pinned to its tag's commit: Dashboard →
Features → Official add-ons → **Add**, `/addons official` on Telegram, or `kurooto addons add <name>`. The card comes
first, as for any add-on by link (docs/wiki/user/add-ons.md#official-add-ons).

| Folder | Repository | Feature | What it does | Starts |
|---|---|---|---|---|
| `restic-backups/` | [kurooto-restic-backups](https://github.com/avtarfr/kurooto-restic-backups) | Machine backups (restic) | backs up your folders with restic, thins out and checks | restic |
| `desktop-helpers/` | [kurooto-desktop-helpers](https://github.com/avtarfr/kurooto-desktop-helpers) | Desktop helpers | rings the phone (KDE Connect) and wakes the screen at the alarm; pings | kdeconnect-cli, hyprctl, swaymsg, xset |
| `habits/` | [kurooto-command-words](https://github.com/avtarfr/kurooto-command-words) | Your command words | your own short words for commands and requests (`/j` for `/journal`) | nothing |
| `handwriting-pull/` | [kurooto-handwriting-pull](https://github.com/avtarfr/kurooto-handwriting-pull) | Handwriting from the cloud | copies new handwritten pages from a cloud folder with rclone | rclone, nmcli |
| `night-performance/` | [kurooto-night-performance](https://github.com/avtarfr/kurooto-night-performance) (not in the official list yet) | Night performance | switches to the highest performance power mode during the heavy night work, and back; a root helper for Lenovo Legion and LOQ in `legion/` | powerprofilesctl, tuned-adm, asusctl, system76-power, sudo (-n only), powercfg, pmset |

**A new version:** change the folder here, bump `version` in its manifest, copy the folder's contents to its
repository, tag it (`v1.0.1`), then in `official_addons.json` move the old `commit` into `earlier` and put the new
tag and commit in. Those who have it are offered the update after their Kurooto updates (never applied without their
yes). `tests/unit/test_addon_packages.py` checks that the list matches these folders (names, titles, versions); a folder not
listed yet is named in its `UNLISTED` (take it out when you pin it).


Every one has its manifest (`kurooto-addon.json`, the card you agree to), a README and tests. They run inside Kurooto
with a pretend home: `uv run pytest addons/` here (`conftest.py` adds each one by link, as a user would), and
`tests/unit/test_addon_packages.py` checks that each loads with exactly what its card says. None of them reaches a
host on the internet itself; the programs they start are named on their cards.

How to write one: docs/wiki/dev/modules.md, "Add-ons by link".
