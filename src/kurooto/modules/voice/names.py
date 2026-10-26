"""Hearing its name, the default way to wake Kurooto. Whisper often spells an unusual name wrong ("Kuroto", "kuro
to"), so a name counts when what was written out is:

    1. the name itself, or a spelling you added (voice.listen.name_variants), or, for the default name "Kurooto", one
       of the mishearings in MISHEARD; spaces don't matter ("kuro to" is "kuroto"), so one, two or three words in a
       row can make it;
    2. close enough to the name itself (never to a mishearing, which would let "kurt" through "kuroto"): the same
       consonant skeleton (skeleton(): k/c/q/g as one sound, t/d, r/l, b/p, v/f, s/z; vowels, h, w and y dropped;
       doubles once), at least two vowel groups and no more than one apart from the name's, 4 letters or more, and
       an edit distance of 2 or less.

Whisper is also nudged toward the right spelling (audio.py: the name as its initial prompt and hotword).

called() is the name used as a call: first ("Kurooto, what's due?", "hey kuro, ...") or last ("..., Kurooto?");
anywhere() finds it in passing; uncall() takes the call off ("hey Kurooto, what's due" -> "what's due")."""

from __future__ import annotations

import re

CALLS = ("hey", "hi", "hello", "ok", "okay", "yo", "oi", "listen", "so")
MAX_WORDS = 3  # a name heard as up to three words ("coo ro to")
MISHEARD = {  # the default name, as transcribers write it
    "kurooto": (
        "kuroto",
        "kurouto",
        "kuruto",
        "kurutto",
        "kurotto",
        "kurroto",
        "kurato",
        "kuroot",
        "curoto",
        "curooto",
        "kuro to",
        "kuroo to",
        "coo roto",
        "cu roto",
        "kirito",
        "kiroto",
        "guru to",
        "guruto",
        "kuroo",
        "kuro",
        "kuroda",
        "kurota",
    )
}


def norm(text: str) -> list[str]:
    """Lower case words, punctuation out."""
    return re.sub(r"[^\w' ]+", " ", (text or "").lower()).replace("'", "").split()


def skeleton(word: str) -> str:
    """The word's consonants, as they sound alike (see the module's note)."""
    same = {"c": "k", "q": "k", "g": "k", "d": "t", "l": "r", "b": "p", "v": "f", "z": "s"}
    out = []
    for ch in word.lower():
        if ch in "aeiouyhw" or not ch.isalpha():
            continue
        ch = same.get(ch, ch)
        if not out or out[-1] != ch:
            out.append(ch)
    return "".join(out)


def vowel_groups(word: str) -> int:
    return len(re.findall(r"[aeiouy]+", word.lower()))


def distance(a: str, b: str) -> int:
    """Levenshtein's edit distance."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class NameMatcher:
    def __init__(self, names: list[str], variants: list[str] | tuple[str, ...] = ()):
        canon = []
        for n in names:
            joined = "".join(norm(n))
            if joined and joined not in canon:
                canon.append(joined)
        self.names = canon  # the name itself (and the default's), joined: fuzzy matching is against these only
        spell = set(canon)
        for n in canon:
            spell |= {"".join(norm(v)) for v in MISHEARD.get(n, ())}
        spell |= {"".join(norm(v)) for v in variants or ()}
        self.spellings = {s for s in spell if s}

    def word(self, joined: str) -> bool:
        """Is this (one to three words, joined) the name?"""
        if joined in self.spellings:
            return True
        if len(joined) < 4:
            return False
        groups = vowel_groups(joined)
        for n in self.names:
            if len(n) < 4 or groups < 2 or abs(groups - vowel_groups(n)) > 1:
                continue
            if skeleton(joined) == skeleton(n) and distance(joined, n) <= 2:
                return True
        return False

    def _span_at(self, w: list[str], start: int) -> int:
        """How many words from `start` make the name (0: none); longer first."""
        for k in range(min(MAX_WORDS, len(w) - start), 0, -1):
            if self.word("".join(w[start : start + k])):
                return k
        return 0

    def _span_end(self, w: list[str]) -> int:
        for k in range(min(MAX_WORDS, len(w)), 0, -1):
            if self.word("".join(w[len(w) - k :])):
                return k
        return 0

    def called(self, text: str) -> bool:
        w = norm(text)
        if not w:
            return False
        first = 1 if len(w) > 1 and w[0] in CALLS else 0
        return bool(self._span_at(w, first) or self._span_end(w))

    def anywhere(self, text: str) -> bool:
        w = norm(text)
        return any(self._span_at(w, i) for i in range(len(w)))

    def uncall(self, text: str) -> str:
        """The words with the call taken off: the name (and a "hey" before it) at the start, or the name at the end."""
        words = (text or "").split()
        w = norm(text)
        if len(w) != len(words):  # punctuation-only pieces: keep the text as it is but for a leading call
            words = [x for x in words if norm(x)]
            if len(words) != len(w):
                return text.strip()
        first = 1 if len(w) > 1 and w[0] in CALLS else 0
        k = self._span_at(w, first)
        if k:
            return " ".join(words[first + k :]).lstrip(" ,.!?;:-").strip()
        k = self._span_end(w)
        if k:
            return " ".join(words[: len(words) - k]).rstrip(" ,;:-").strip()
        return text.strip()
