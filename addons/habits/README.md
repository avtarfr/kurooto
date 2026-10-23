# Your command words, a Kurooto add-on

Keep the short words you're used to typing. A word of yours stands for a command or the start of a request, and
typing it works as if you'd typed what it stands for:

```
/words add j = /journal         /j had a good day          → /journal had a good day
/words add deep = high:         /deep why does this fail   → high: why does this fail
/words add rem = remind me      /rem at 9 to call home     → remind me at 9 to call home
```

What a word stands for goes through Kurooto exactly as if you'd typed it, with the same rules (anything that needs
your tap still does). A word can't stand for another word, and a command Kurooto or a feature already has can't be
taken as a word.

## Add it

```
kurooto addons add https://github.com/avtarfr/kurooto-command-words --ref v1.0.0
```

or Dashboard → Features → **Add-ons by link**; read the card, Add, then turn on **Your command words**.

## Its card

| | |
|---|---|
| Adds | the feature `habits`; the command `/words`, and each word you add yourself as a command |
| May reach | nothing on the internet |
| May start | no programs |
| Runs code | yes: one Python file, run inside Kurooto |

## Commands

| Command | Does |
|---|---|
| `/words` | your words and what each stands for |
| `/words add j = /journal` | adds a word (`=`, `as` or `->`) |
| `/words remove j` | takes one away |

## Settings

| Setting | Default | Effect |
|---|---|---|
| `habits.words` | `{}` | your words, e.g. `{"j": "/journal", "deep": "high:"}` |

## Remove it

Turn it off, then `kurooto addons remove habits` (`kurooto addons undo habits` puts it back). Your words stay in
your settings.

## Tests

Inside a Kurooto checkout, with this folder at `addons/habits/`: `uv run pytest addons/habits`.
