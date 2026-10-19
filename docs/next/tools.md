# tools: docs to merge (0.2.0)

## MANUAL: new section after "Your AI brain"

### What the AI can do (its tools)

Your AI doesn't only answer: it can act, the same way on a phone call, in Chat, and in background requests. It
adds a reminder, calls you back later, holds calls, adds a deadline, logs study time, creates a note or adds to one,
ticks a `- [ ]` task, and asks you a question when it needs your answer. Each feature you turn on adds its own
tools; a feature that's off has none. The notes tools never change what you wrote: they create new notes, add text
at the end of a note or one of its sections, and tick tasks. Nothing is sent to anyone but you.

- **API brains** (Gemini key, Ollama, Custom) call the tools directly. A model that can't use tools
  (some small Ollama models) just answers without them.
- **Agent programs** (agy, Codex, Claude Code) get them through `kurooto mcp`, a small MCP server that passes each
  call to the running Kurooto. Codex and Claude Code get it for each request only; nothing is saved in their own
  settings. agy gets it once, when you test agy on the setup page (or before its first request after this update):
  Kurooto runs `agy mcp add kurooto ...` and adds `mcp(kurooto/*)` to agy's allow-list
  (`~/.gemini/antigravity-cli/settings.json`, backed up first to Kurooto's state folder → `backups/`).
- **Your own agent sessions** can use them too: add `kurooto mcp` as an MCP server in any MCP client. It works
  while Kurooto is running.
- The AI is told to say plainly when it couldn't do something, never to claim it did.

*Turn it off:* the tools come from the features you have on; turn a feature off and its tools go. To take them away
from agy: `agy mcp remove kurooto`, and delete the `mcp(kurooto/*)` line from agy's settings.
*Leaves your computer:* nothing new. What a tool returns (a note's text, your deadlines) goes to the AI you picked,
like the notes it reads.

### AI usage (/usage)
`/usage` (with Chat on) lists AI requests per day over the last 7 days (`/usage 14` for two weeks), per brain, and
how often a usage limit was hit, from Kurooto's own request log. Quick checks (how hard a request is, grading a quiz
answer) and phone calls aren't counted.

## MANUAL: "Other programs can message you" gains

### From a terminal or a script
- `kurooto ask "what's due this week?"`: plain English, as on Telegram. Quick things (reminders, holds, what's due,
  /commands) answer at once; anything bigger goes to your AI and its answer prints here, not on Telegram.
  `kurooto ask` alone opens a prompt where you type one request after another. `--no-wait` prints the request's id;
  `kurooto ask --job <id>` waits for its answer later.
- `kurooto call "the backup finished"`: rings your phone (needs Phone calls). It waits out your no-call rules
  (classes, /hold, focus, night) and calls when they end; `--force` rings now anyway, `--alarm` rings as a wake-up
  alarm, `--at 17:30` (or "in 20 min", "tomorrow 7:00") calls later. Nothing ever rings while you're on a call.
- `kurooto mcp`: Kurooto's tools for agent programs (above).
All three need Kurooto running.

## MANUAL: Chat section, add
`/usage` shows how many AI requests ran each day and the limits hit.

## Troubleshooting rows
| What you see | What to do |
|---|---|
| The setup page says agy "can't use Kurooto's tools yet" | agy's settings file isn't plain JSON, or `agy mcp add` failed. Add `mcp(kurooto/*)` to `permissions.allow` in `~/.gemini/antigravity-cli/settings.json` yourself, then Test again. |
| The AI said it did something but nothing happened | Tell it so; check `/jobs`. With a small local model, tools may not be supported: it answers without them. |
| `kurooto ask` / `kurooto call` say Kurooto isn't running | `kurooto on`. |
| An agent program says Kurooto's tools aren't running | Kurooto is off or restarting; `kurooto on`, then ask again. |

## CHANGELOG lines (0.2.0)
- The AI can act, not just answer: every feature's tools (reminders, calls, deadlines, study log, notes, questions to
  you) reach API brains directly and agent programs (agy, Codex, Claude Code) through `kurooto mcp`, a built-in MCP
  server. The notes tools only create, add to and tick; they never change what you wrote.
- `kurooto ask` (plain English from a terminal, with a prompt mode), `kurooto call` (ring your phone now or later,
  respecting your no-call rules) and `kurooto mcp`.
- `/usage`: AI requests per day per brain over the last week, and usage limits hit.
- Long requests to agy no longer fail on Windows' command-line limit (they go through a temporary file).

## PRIVACY notes
- Tools add no new destination. What a tool returns to the AI (a note's text, your reminders or deadlines) goes to
  the AI service you picked, as notes it reads always did.
- `kurooto mcp` talks only to Kurooto on 127.0.0.1, with a key that is good for the tools and nothing else; it
  changes at every start and is kept in an owner-only file in Kurooto's state folder (`tools-access.json`).
- agy's settings file is changed in one place (`mcp(kurooto/*)` added to its allow-list), after a backup.
- A long agy request is written for the length of the run to `.kurooto/requests/` inside your notes folder (a git-
  ignored hidden folder, so Notes sync never uploads it), then deleted.

## Settings
None new. Environment: `KUROOTO_AGY_TOOLS=1` lets a portable copy (KUROOTO_HOME set) register its tools with agy by
itself; otherwise only the setup page's agy test does that for portable copies.

## Terms review (maintainer-approved): changes outside my own sections

### MANUAL, "Your AI brain" table
- Delete the **FreeLLMAPI** row.
- Gemini API key row, "Good for" column: "simplest; also needed for calls and voice notes. Free tier: Google may
  use what you send to improve its products and human reviewers may read it; 18+; in the EEA, UK and Switzerland a
  paid key is required (use a paid key if you don't want that)".
- After the table, add: "**agy:** Kurooto runs Google's official agy program on your computer, signed in as you, and
  never touches its sign-in token. Google's answers differ on whether other tools may start agy unattended, so there is
  some risk to your Google account; for tools like Kurooto, Google recommends a Gemini API key."
- And: "An AI set up as FreeLLMAPI with an earlier version keeps working; it now shows as 'Another OpenAI-compatible
  service'."

### README.md line 42
"**AI, your choice:** Antigravity (agy), a Gemini key, ChatGPT/Codex, Claude Code, any OpenAI-compatible service, or
local models" (drop FreeLLMAPI).

### AGENTS.md
No FreeLLMAPI mention there. Line 83's example ("a free Gemini key" as the fallback) can stay; if you want it
precise: "a Gemini key (free tier: see PRIVACY.md)".

### docs/PRIVACY.md
Done directly on w/tools: the Chat row no longer names FreeLLMAPI, and "Free tiers" became "Free tiers and terms"
(the Gemini free-tier points, the agy line, FreeLLMAPI no longer offered).

### CHANGELOG (0.2.0)
- FreeLLMAPI is no longer offered as an AI (it pools other providers' free tiers); one set up earlier keeps working
  and shows as "Another OpenAI-compatible service".
- The setup page says plainly what a free Gemini key means (Google may use and review what you send; 18+; a paid key
  in the EEA, UK and Switzerland) and what using agy through Kurooto means for your Google account.

## The ★ moves to the Gemini key (maintainer's decision)

### MANUAL, "Your AI brain" table: new order and ★
| Brain | Cost | Good for | Setup |
|---|---|---|---|
| **Gemini API key** ★ | free tier, or paid | the simplest, and the way Google recommends for tools like this; also used for calls and voice notes. Free tier: Google may use what you send to improve its products and human reviewers may read it; 18+; a paid key is required in the EEA, UK and Switzerland | [Google AI Studio](https://aistudio.google.com/apikey) → Create API key → paste |
| **Antigravity (agy)** | free with a Google account | Google's agent program on your computer; can read your notes. Some risk to the Google account (see the note below the table) | Install → a window opens → sign in with Google |
| **ChatGPT / Codex** | needs a paid ChatGPT plan | if you already pay for ChatGPT | Install → sign in with your ChatGPT account |
| **Claude Code** (Advanced) | needs a paid Claude plan | if you already pay for Claude | Install → sign in with your Claude account |
| **Local (Ollama)** | free | private and offline, but much weaker | only offered on computers with a graphics card or Apple Silicon |
| **Custom** | depends | any OpenAI-compatible service | its address, key and model names |

Keep the agy note from the terms-review section under the table. Add: "If you set Kurooto up before 0.2.0, it keeps
the AI you chose."

### README
"**AI, your choice:** a Gemini API key (recommended), Antigravity (agy), ChatGPT/Codex, Claude Code, local models, or
any OpenAI-compatible service".

### CHANGELOG (0.2.0)
- The setup page now recommends a Gemini API key as the AI (the simplest, and Google's recommended route for tools),
  then agy, Codex, Claude Code, local models and custom. Existing setups keep the AI they chose.

### Done directly on w/tools
docs/friend-test.md: session 1 step 4 is now the Gemini key ★ (AI Studio → Create API key → paste → Test); session 2
step 1 notes the key is already saved from session 1.
