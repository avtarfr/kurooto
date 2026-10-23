# Desktop helpers, a Kurooto add-on

Small things around Kurooto's alarm and messages on a desktop computer:

- **At the alarm**, your phone rings through [KDE Connect](https://kdeconnect.kde.org) too (handy when it's on silent
  in another room), and the screen wakes (Hyprland, Sway or X11).
- **A message comes**: a short KDE Connect ping to your phone for the kinds you pick (`deadline`, `reminder`, ...).
  Only "Kurooto: deadline" is sent, never the message itself.
- **`/findphone`** rings your phone now.

## Add it

```
kurooto addons add <this repository's git address> --ref v1.0.0
```

or Dashboard → Features → **Add-ons by link**; read the card, Add, then turn on **Desktop helpers**. It needs KDE
Connect paired with your phone (for the rings and pings), or a Hyprland, Sway or X11 session (for the screen).

## Its card

| | |
|---|---|
| Adds | the feature `desktop_helpers`; the command `/findphone` |
| May reach | nothing on the internet (KDE Connect talks to your phone over your own network) |
| May start | `kdeconnect-cli`, `hyprctl`, `swaymsg`, `xset` |
| Runs code | yes: one Python file, run inside Kurooto |

## Settings (Dashboard → Settings → desktop_helpers)

| Setting | Default | Effect |
|---|---|---|
| `desktop_helpers.phone` | empty | your phone's KDE Connect name or id (empty: the first one it can reach) |
| `desktop_helpers.ring_on_alarm` | on | ring the phone when the alarm rings |
| `desktop_helpers.wake_screen_on_alarm` | on | wake the screen when the alarm rings |
| `desktop_helpers.ping_kinds` | `[]` | kinds of messages that also ping the phone: `info`, `result`, `reminder`, `deadline`, `question`, `approval` |

## Remove it

Turn it off, then `kurooto addons remove desktop-helpers` (`kurooto addons undo desktop-helpers` puts it back).

## Tests

Inside a Kurooto checkout, with this folder at `addons/desktop-helpers/`: `uv run pytest addons/desktop-helpers`.
Fake `kdeconnect-cli` and `hyprctl` stand in.
