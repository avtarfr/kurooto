"""What may feed the mind's reward, and what never may (invariant I-3: engagement never reaches reward).

REWARD_SOURCES names the only modules whose data a reward module may read: the body budget's variables, promises,
whether AI requests succeeded, Kurooto's own health and vitals, and the forecast's skill scores. A reward module
(one that sets `REWARD = True` at its top, from stage 05) may import nothing else from Kurooto
(test_reward_whitelist_imports reads its imports).

BANNED_FIELDS and BANNED_KINDS are the engagement signals: how often or how fast you reply, how long you talk to it,
how often you open the app, how you feel about Kurooto, and its reads of your mood or state. The scorekeeper drops
these fields from everything it's sent, and nothing that scores may read them (test_fake_engagement_moves_nothing).
"""

from __future__ import annotations

# the names, as the spec writes them, and the Kurooto modules they are
REWARD_SOURCES = frozenset(
    {
        "mind.budget",
        "mind.promises",
        "core.jobs",  # success or failure only
        "core.health",
        "core.vitals",  # health numbers only
        "mind.forecast",  # skill scores only
    }
)
REWARD_MODULES = frozenset(f"kurooto.{s}" for s in REWARD_SOURCES)
# the mind's own plumbing a reward module may also use: the log, its records, this list, the scorekeeper's tables
MIND_PLUMBING = frozenset(
    {"kurooto.mind", "kurooto.mind.log", "kurooto.mind.records", "kurooto.mind.whitelist", "kurooto.mind.score"}
)

BANNED_FIELDS = frozenset(
    {
        "reply_count",
        "replies",
        "reply_latency",
        "reply_s",
        "latency",
        "session_length",
        "session_s",
        "chat_time",
        "chat_s",
        "app_open",
        "app_opens",
        "app_open_s",
        "sentiment",
        "sentiment_to_kurooto",
        "mood",
        "state_read",
        "valence_owner",
        "engagement",
    }
)
BANNED_KINDS = frozenset(
    {
        "message_in",
        "chat_message",
        "app_opened",
        "app_closed",
        "session_ended",
        "mood_read",
        "state_read",
        "tone_tag",
    }
)


def is_banned(key: str) -> bool:
    return key in BANNED_FIELDS


def allowed_import(module: str) -> bool:
    """May a reward module import this? The standard library, the reward sources and the mind's plumbing."""
    if not module.startswith("kurooto"):
        return True
    return any(module == m or module.startswith(m + ".") for m in REWARD_MODULES) or module in MIND_PLUMBING
