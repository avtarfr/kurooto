# ruff: noqa: E501
"""Settings that take one of a few values (0.8.0): the dashboard shows each as a drop-down, not a box to type a word into.

`CHOICES` maps "section.key" to [[value, what it means], ...]. A test checks each default is one of its choices, so a typo here
can't make a setting show a value it can't have. Settings whose values are open (a path, a name, a number, a model) stay boxes.
"""

from __future__ import annotations

DAYS = [[d, d] for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")]
LEVELS = [["low", "low"], ["medium", "medium"], ["high", "high"]]
AI3 = [["local", "local: this computer's model"], ["main", "main: your AI"], ["off", "off"]]
EMB = [["auto", "auto"], ["ollama", "ollama: a model on this computer"], ["gemini", "gemini: your key"], ["off", "off"]]

CHOICES: dict[str, list[list[str]]] = {
    "look.board": [
        ["being", "being: Kurooto as one living body, its work lighting up as it happens (0.8.9)"],
        ["three", "three: NOTES, SYSTEMS and BRAIN on top, STATUS and TERMINAL below"],
        ["classic", "classic: STATUS down the left (before 0.8.3)"],
    ],
    "look.being_theme": [["void", "void: white light on black"], ["theme", "theme: the page's palette"]],
    "look.brain_monitor": [
        ["shown", "shown: the part monitor stays beside the model"],
        ["drawer", "drawer: it slides out from a tab"],
    ],
    "autostart.when": [["login", "login"], ["boot", "boot: before anyone logs in (Linux with systemd)"]],
    "books.latex": [["maths", "maths: pages whose maths came out in pieces"], ["all", "all pages"], ["never", "never"]],
    "books.ocr": [
        ["auto", "auto: Tesseract, else the vision model"],
        ["tesseract", "tesseract"],
        ["vision", "vision model"],
        ["off", "off"],
    ],
    "brain.agy.io_mode": [["pipe", "pipe"], ["pty", "pty: a pseudo-terminal, where pipes give no output"]],
    "calendar.nocall_events": [
        ["all", "all: every timed event holds calls"],
        ["tagged", "tagged: #nocall ones and no-call calendars"],
    ],
    "calls.chat_titles": [
        ["first words", "first words: of the chat's first message"],
        ["ai", "ai: a short title the AI writes"],
    ],
    "calls.review_effort": LEVELS,
    "calls.turn_brain": [["gemini", "gemini: your key"], ["local", "local: Local AI models"]],
    "dreaming.consolidate_ai": AI3,
    "dreaming.fold_ai": AI3,
    "gbrain.embeddings": EMB,
    "gbrain.mcp_surface": [["full", "full"], ["starter", "starter"], ["verbs", "verbs"]],
    "handwritten.keep_original": [["copy", "copy: next to the note"], ["link", "link: leave it where it is"]],
    "infer.sweep_ai": AI3,
    "integrate.embeddings": EMB,
    "integrate.order": [["smallest", "smallest: fewest pages first"], ["name", "name"]],
    "integrate.rerank": [["auto", "auto"], ["off", "off"]],
    "look.design": [["new", "new"], ["classic", "classic: the monospace look of 0.5.18"]],
    "mail_digest.confidential": [
        ["count", "count: only how many"],
        ["local", "local: summarised by a model on this computer"],
    ],
    "mind.finetune.day": DAYS,
    "privacy.egress": [
        ["record", "record: count every request"],
        ["enforce", "enforce: refuse hosts not on the list"],
        ["off", "off"],
    ],
    "projects.effort": [*LEVELS, ["auto", "auto"]],
    "quota.local": [["quick", "quick"], ["background", "background"], ["off", "off"]],
    "skills.auto_pack": [["ask", "ask: a button"], ["auto", "auto: build it"], ["off", "off"]],
    "terminal.default_opens": [["shell", "shell: one tab"], ["layout", "layout: all tabs"]],
    "terminal.top": [["left", "left: a column beside the first tab"], ["tab", "tab: a tab of its own"], ["off", "off"]],
    "voice.speak.ack": [
        ["tone", "tone: a short soft note"],
        ["word", 'word: "Hmm." in its own voice'],
        ["off", "off"],
    ],
    "voice.listen.fast_brain": [
        ["same", "same: your AI, as always"],
        ["local", "local: plain chat to this computer's model"],
        ["fastest", "fastest: plain chat to the quickest AI set up"],
    ],
    "voice.listen.need_face_fallback": [
        ["voice", "voice: its voice rules alone"],
        ["none", "none: nothing by voice until the camera sees"],
    ],
    "voice.speaker_id.mode": [  # (voice id)
        ["owner_only_acts", "owner_only_acts: others may chat"],
        ["owner_only_at_all", "owner_only_at_all: others get one line, nothing else"],
    ],
    "voice.speaker_id.model": [
        ["campplus-en", "campplus-en: English, most accurate"],
        ["campplus-multi", "campplus-multi: English and other languages"],
    ],
    "voice.speaker_id.strictness": [["relaxed", "relaxed"], ["normal", "normal"], ["strict", "strict"]],
    "voice.speaker_id.guest_brain": [["main", "main: your AI, none of your data"], ["local", "local: this computer"]],
}


def for_section(section: str) -> dict[str, list[list[str]]]:
    p = section + "."
    return {k[len(p) :]: v for k, v in CHOICES.items() if k.startswith(p)}
