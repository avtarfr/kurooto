"""Mail digest: twice a day, your new Gmail sorted into Needs action, People, Courses, Opportunities and Admin, sent to
you with a copy in your notes (mail/). Deadlines it finds go into Deadlines. Gmail is only read: nothing is sent,
deleted, archived or marked read.

What the AI may read is up to you. Everything else is only counted: never summarised, and its text never leaves this
computer (Kurooto looks only at its sender, subject and Gmail labels, here, to sort it).
- mail from senders or labels you choose:  /mail read @school.example   /mail read label:Courses
  /mail read sam@example.org   (/mail unread ... takes one off; /mail rules lists them)
- on a school or work Google account, mail from your own organisation's domain (setting mail_digest.own_domain)
Even then, personal mail (not about study or work) is only counted unless it comes from a sender or label you chose.
Opt-in (mail_digest.confidential = "local"): mail marked confidential is summarised by a local model instead, on this
computer only (google_confidential.py).
Promotions, Social and topics on your not-interested list are only counted.
Mail marked confidential is never read, whoever sent it: "confidential", "do not forward", "restricted" or a standard
confidentiality footer ("if you are not the intended recipient", ...) anywhere in its subject, its text or a Gmail
label's name (mail_digest.confidential_words). Nor is mail from a sender, domain or label on your never-read list
(/mail never ...). Work or school mail may be covered by
your institution's email policy; these are only counted, never summarised, and get no AI reply drafts.

Email reply drafts (a feature of its own): when the digest finds mail that needs your reply, the AI drafts one into
your Gmail Drafts and sends it to you with Send / Edit / Discard. Nothing is sent unless you tap Send. Edit: say what
to change; the AI rewrites it and asks again.

Mail digest by email (a feature of its own): each digest also comes to your own inbox, sent from the Google account
you choose (a personal one, say, while the digest reads a school one) to that account's own address and nobody
else's. A digest that mentions confidential material isn't emailed (it still comes on Telegram).
"""

from __future__ import annotations

import base64
import datetime as dt
import functools
import html
import re
import time
from collections import Counter
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path

from kurooto.core import layout
from kurooto.core.clock import now
from kurooto.core.config import register_defaults
from kurooto.core.lock import Lock, Timeout
from kurooto.core.state import jload, jsave
from kurooto.modules import google_confidential as local
from kurooto.modules.base import Command, Incoming
from kurooto.modules.calls.tools import Tool, arg, clip
from kurooto.modules.google import (
    GoogleError,
    GooglePart,
    NeedsSignIn,
    not_interested,
    not_interested_list,
    run_skill,
)

register_defaults(
    "mail_digest",
    {
        "at": "daily 08:00,18:00",
        "read": [],  # what the digest may read: "label:Courses", "sam@example.org", "@school.example"
        "own_domain": True,  # on a school or work account, mail from your own domain is read too
        "first_days": 3,  # the first digest looks this far back
        "max_messages": 200,  # per check
        "save_note": True,  # a copy of each digest in your notes (mail/<date>-<time>.md, or your notes layout's place)
        # mail marked confidential is only counted: never read by the AI, summarised or answered with a draft
        "skip_confidential": True,
        "confidential_words": [  # regular expressions, any case; a space matches any run of spaces or line breaks
            "confidential",
            "do not forward",
            "restricted",
            "private and confidential",
            "privileged and confidential",
            "proprietary and confidential",
            "intended (solely|only) for the (use of the )?(addressee|individual|recipient|person)",
            "if you are not the intended recipient",
            "this (e-?mail|message|communication) (and any attachments? )?(is|are|may be|contains?) (strictly )?"
            "(confidential|privileged)",
        ],
        "never_read": [],  # senders, @domains or label:Name the digest never reads, even if chosen above
        # mail marked confidential: "count" (only counted) or "local" (summarised by a local model on this computer,
        # kept only in Kurooto's data folder; needs Local AI models)
        "confidential": "count",
        "local_model": "",  # which Ollama model reads it; empty: Local AI models' helper model
    },
)
register_defaults("reply_drafts", {"per_day": 5, "ask_days": 3})
GMAIL = "https://gmail.googleapis.com"  # noqa: S105 (an address)
CONSUMER = {"gmail.com", "googlemail.com"}  # a personal account: no "own domain"
NOREPLY = re.compile(r"no-?reply|do-?not-?reply|mailer-daemon|postmaster|bounce", re.I)
RULE = re.compile(r"^(label:\S.*|[^@\s]+@[^@\s]+\.[^@\s]+|@[^@\s]+\.[^@\s]+)$", re.I)
PER_BATCH = 20  # messages per AI request
MAX_TEXT = 3000  # characters of each message


# ------------------------------------------------------------------------------------------------ mail text
def _b64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def html_to_text(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", "", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", s)
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def _texts(payload: dict) -> tuple[list[str], list[str]]:
    """Every text/plain part, and every HTML part as text."""
    plain, rich = [], []

    def walk(p: dict) -> None:
        mime, data = p.get("mimeType", ""), (p.get("body") or {}).get("data")
        if data and not p.get("filename"):
            if mime == "text/plain":
                plain.append(_b64(data).decode("utf-8", "replace"))
            elif mime == "text/html":
                rich.append(html_to_text(_b64(data).decode("utf-8", "replace")))
        for c in p.get("parts") or []:
            walk(c)

    walk(payload)
    return plain, rich


def whole_text(payload: dict) -> str:
    """All of a message's text, quoted replies and footers included (what the confidentiality check reads)."""
    plain, rich = _texts(payload)
    return "\n".join(plain + rich)


@functools.lru_cache(maxsize=16)
def marking(words: tuple[str, ...]) -> re.Pattern | None:
    """One pattern for the confidentiality markings: each a regular expression (or plain words, if it isn't a valid
    one), any case, a space matching any whitespace, whole words only."""
    parts = []
    for w in (x.strip() for x in words if x and x.strip()):
        src = re.sub(r" +", r"\\s+", w)
        try:
            re.compile(src)
        except re.error:
            src = re.escape(w).replace(r"\ ", r"\s+")
        parts.append(f"(?:{src})")
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.I) if parts else None


def body_text(payload: dict) -> str:
    """The message's own words: plain text if there is some (else the HTML's text), without quoted replies."""
    plain, rich = _texts(payload)
    text = "\n".join(plain) if plain else "\n".join(rich)
    text = re.split(r"\n\s*On .{5,200}wrote:\s*\n", text)[0]
    text = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(">"))
    return clip(re.sub(r"\n{3,}", "\n\n", text).strip(), MAX_TEXT)


def attachment_names(payload: dict) -> list[str]:
    out: list[str] = []

    def walk(p: dict) -> None:
        if p.get("filename"):
            out.append(p["filename"])
        for c in p.get("parts") or []:
            walk(c)

    walk(payload)
    return out[:20]


def headers(msg: dict) -> dict:
    return {h["name"].lower(): h.get("value", "") for h in (msg.get("payload") or {}).get("headers", [])}


def domain_of(addr: str) -> str:
    return addr.rsplit("@", 1)[-1].lower() if "@" in addr else ""


# ---------------------------------------------------------------------------------------------- the digest
class MailDigest(GooglePart):
    id = "mail_digest"
    part = "mail_digest"
    title = "Mail digest"
    description = (
        "Twice a day, your new mail sorted into Needs action, People, Courses, Opportunities and Admin; deadlines "
        "into Deadlines. Personal mail is only counted."
    )
    privacy = (
        "Reads Gmail (read-only: nothing is sent, deleted or marked read). Only mail from senders or labels you chose "
        "(and, on a school or work account, your own domain) is read and goes to the AI you picked; the rest is only "
        "counted, on this computer. Mail marked confidential is never read."
    )
    permission = (
        "Google will ask you to allow Kurooto to read your email (read-only: it can't send, delete or change "
        "anything). Kurooto reads only the mail you choose for the digest (/mail read ...); the rest it only counts."
    )
    api_link = ("Turn on the Gmail API", "https://console.cloud.google.com/apis/library/gmail.googleapis.com")

    @property
    def dir(self) -> Path:
        return self.app.paths.state / "mail-digest"

    def start(self):
        self.every("digest", self.setting("at") or "daily 08:00,18:00", self.digest)
        self.app.jobs.then_actions["mail_digest.done"] = self._done

    # ------------------------------------------------------------------------------------------ sorting
    def me(self) -> str:
        st = jload(self.dir / "state.json", {}) or {}
        if st.get("account", "main") != self.account:  # you moved the digest to another account: start afresh there
            st = {"account": self.account}
        if not st.get("me"):
            st["me"] = (self.google.api("gmail", "/users/me/profile").get("emailAddress") or "").lower()
            jsave(self.dir / "state.json", st)
        return st["me"]

    def rules(self, key: str = "read") -> list[str]:
        return [str(r).strip() for r in self.setting(key) or [] if str(r).strip()]

    @staticmethod
    def matches(rule: str, addr: str, labels: set[str]) -> bool:
        """Does a rule ("label:Name", "sam@example.org", "@example.org") cover this sender or one of these labels?"""
        low, dom = rule.lower(), domain_of(addr)
        if low.startswith("label:"):
            return low[6:].strip() in labels
        if low.startswith("@"):
            return dom == low[1:] or dom.endswith("." + low[1:])
        return addr == low

    def marked(self, *texts: str) -> str | None:
        """The confidentiality marking in these texts (subject, whole body, label names), or None."""
        pat = marking(tuple(str(w) for w in self.setting("confidential_words") or []))
        for t in texts if pat else ():
            m = pat.search(t or "")
            if m:
                return re.sub(r"\s+", " ", m.group(0)).lower()
        return None

    def confidential(self, *texts: str) -> str | None:
        """marked(), when the check is on (it is unless you turned mail_digest.skip_confidential off)."""
        return self.marked(*texts) if self.setting("skip_confidential") else None

    def blocked(self, frm: str, subject: str, labels: set[str]) -> str | None:
        """Why this mail must never reach the AI (on your never-read list, or marked confidential in its subject or
        labels), or None. The body is checked once it's downloaded, before anything else happens to it."""
        addr = parseaddr(frm)[1].lower()
        if any(self.matches(r, addr, labels) for r in self.rules("never_read")):
            return "never read"
        if self.confidential(subject, *labels):
            return "confidential"
        return None

    def own_domain(self, me: str) -> str:
        d = domain_of(me)
        return d if d and d not in CONSUMER and self.setting("own_domain") else ""

    def triage(self, frm: str, subject: str, label_ids: list[str], names: dict, me: str) -> tuple[str, str, bool]:
        """("read", why, chosen-by-you) or ("count", which pile, False). Only the sender, subject and labels are
        looked at, on this computer."""
        name, addr = parseaddr(frm)
        addr = addr.lower()
        dom = domain_of(addr)
        if not_interested(self.app, f"{subject} {name}"):
            return "count", "not interested", False
        labels = {names.get(i, i).lower() for i in label_ids}
        stop = self.blocked(frm, subject, labels)
        if stop:
            return "count", stop, False
        for r in self.rules():
            if self.matches(r, addr, labels):
                return "read", f"you chose {r}", True
        if "CATEGORY_PROMOTIONS" in label_ids:
            return "count", "promotions", False
        if "CATEGORY_SOCIAL" in label_ids:
            return "count", "social", False
        own = self.own_domain(me)
        if own and (dom == own or dom.endswith("." + own)):
            return "read", "from your own domain", False
        return "count", "other", False

    # ----------------------------------------------------------------------------------------- fetching
    def fetch(self) -> dict:
        g = self.google
        st = jload(self.dir / "state.json", {}) or {}
        me = self.me()
        st = jload(self.dir / "state.json", {}) or st
        since_ms = st.get("last_ms") or int((now().timestamp() - (self.setting("first_days") or 3) * 86400) * 1000)
        q = f"after:{max(0, since_ms // 1000 - 3600)} -in:chats -in:sent -in:drafts -in:spam -in:trash"
        cap = int(self.setting("max_messages") or 200)
        ids = [
            m["id"]
            for m in g.pages("gmail", "/users/me/messages", "messages", {"q": q, "maxResults": 100}, cap // 100 + 1)
        ]
        seen = dict.fromkeys(st.get("seen", []))  # in order, so the oldest are dropped first
        names = {}  # your labels' names: for label: rules, and labels that mark mail confidential
        if self.setting("skip_confidential") or any(
            r.lower().startswith("label:") for r in self.rules() + self.rules("never_read")
        ):
            names = {x["id"]: x.get("name", "") for x in g.api("gmail", "/users/me/labels").get("labels", [])}
        counted, read, newest = Counter(st.get("counted") or {}), [], since_ms
        known = jload(self.dir / "known.json", {}) or {}
        model = self.local_reader()
        secret: list[dict] = []  # local mode: marked mail for the local model, in memory only
        for mid in list(reversed(ids))[:cap]:  # oldest first
            if mid in seen:
                continue
            meta = g.api(
                "gmail",
                f"/users/me/messages/{mid}?format=metadata&metadataHeaders=From&metadataHeaders=Subject"
                "&metadataHeaders=Reply-To&metadataHeaders=Message-ID&metadataHeaders=Date",
            )
            seen[mid] = None
            newest = max(newest, int(meta.get("internalDate") or 0))
            h = headers(meta)
            if parseaddr(h.get("from", ""))[1].lower() == me:
                continue  # your own
            what, why, chosen = self.triage(
                h.get("from", ""), h.get("subject", ""), meta.get("labelIds", []), names, me
            )
            when = dt.datetime.fromtimestamp(int(meta.get("internalDate") or 0) / 1000)
            if what == "count":
                counted[why] += 1
                if why == "confidential" and model and len(secret) < local.PER_RUN:
                    full = g.api("gmail", f"/users/me/messages/{mid}?format=full")
                    secret.append(self._secret(h, when, whole_text(full.get("payload") or {})))
                continue
            full = g.api("gmail", f"/users/me/messages/{mid}?format=full")
            whole = whole_text(full.get("payload") or {})
            if self.confidential(whole):  # anywhere in it, footers too
                counted["confidential"] += 1
                if model and len(secret) < local.PER_RUN:
                    secret.append(self._secret(h, when, whole))
                del full, whole  # dropped here: never stored, never sent to the cloud AI
                continue
            text = body_text(full.get("payload") or {})
            rec = {
                "id": mid,
                "thread": meta.get("threadId", ""),
                "date": f"{when:%Y-%m-%d %H:%M}",
                "from": h.get("from", ""),
                "subject": h.get("subject", "") or "(no subject)",
                "why": why,
                "chosen": chosen,
                "labels": sorted(names[i] for i in meta.get("labelIds", []) if i.startswith("Label_") and names.get(i)),
                "text": text,
                "attachments": attachment_names(full.get("payload") or {}),
                "link": f"https://mail.google.com/mail/u/0/#all/{meta.get('threadId', '')}",
            }
            read.append(rec)
            known[mid] = {
                "from": h.get("from", ""),
                "reply_to": h.get("reply-to", ""),
                "subject": rec["subject"],
                "msgid": h.get("message-id", ""),
                "thread": rec["thread"],
                "labels": rec["labels"],
                "marked": bool(self.marked(rec["subject"], whole, *rec["labels"])),  # read with the check off
                "text": clip(rec["text"], 1500),
                "at": now().isoformat(),
            }
        if read:
            stamp = f"{now():%Y%m%d-%H%M%S}"
            for n in range(0, len(read), PER_BATCH):
                jsave(
                    self.dir / "batches" / f"{stamp}-{n // PER_BATCH}.json",
                    {
                        "at": now().isoformat(),
                        "messages": read[n : n + PER_BATCH],
                        "counted": dict(counted) if n == 0 else {},
                    },
                )
            st["counted"] = {}
        else:
            st["counted"] = dict(counted)  # told with the next digest
        cutoff = (now() - dt.timedelta(days=30)).isoformat()
        known = dict(
            sorted(((k, v) for k, v in known.items() if v.get("at", "") > cutoff), key=lambda kv: kv[1]["at"])[-2000:]
        )
        jsave(self.dir / "known.json", known)
        st.update(last_ms=newest, seen=list(seen)[-5000:])
        jsave(self.dir / "state.json", st)
        out = {"read": len(read), "counted": sum(counted.values()), "piles": dict(counted)}
        if secret:
            n, dates = local.summarise(self.app, model, secret)
            del secret
            out["summarised_here"] = n
            if n:
                more = f" It found {dates} date(s): /mail confidential to add them." if dates else ""
                self.app.notify(
                    f"Confidential ({n}): summarised on this computer; open the dashboard to read it.{more}",
                    kind="info",
                )
                self.app.events.emit("mail_confidential_local", mails=n, dates=dates)
        elif counted.get("confidential") and self.setting("confidential") == "local" and not model:
            self._no_local_model()
        return out

    def local_reader(self) -> str | None:
        """Local mode: the local model that may read confidential mail, or None (then it's only counted)."""
        if self.setting("confidential") != "local" or not self.setting("skip_confidential"):
            return None
        model = local.local_model(self.app)
        if model:
            (self.dir / "no-local-model").unlink(missing_ok=True)
        return model

    def _no_local_model(self) -> None:
        """Say once (until a local model is back) that confidential mail is only counted for now."""
        flag = self.dir / "no-local-model"
        if flag.exists():
            return
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.touch()
        self.app.notify(
            "Mail digest: confidential mail is only counted for now, because no local model is ready to summarise it "
            "on this computer (turn on Local AI models; they run on the charger). I'll summarise it again once one is.",
            kind="info",
        )

    @staticmethod
    def _secret(h: dict, when: dt.datetime, whole: str) -> dict:
        return {
            "from": h.get("from", ""),
            "subject": h.get("subject", ""),
            "date": f"{when:%Y-%m-%d %H:%M}",
            "text": whole,
        }

    def known(self, mid: str) -> dict | None:
        return (jload(self.dir / "known.json", {}) or {}).get(str(mid))

    def digest(self, p: dict | None = None) -> dict:
        if not self.allowed():
            return {"skipped": "needs Google's OK"}
        try:
            with Lock(self.app.paths.state, "mail-digest", timeout=0):
                try:
                    found = self.fetch()
                except NeedsSignIn:
                    return {"error": "needs sign-in"}
                except Exception as e:
                    self.app.events.emit("mail_digest_failed", error=str(e)[:200])
                    return {"error": str(e)[:200]}
                found["queued"] = self.queue()
        except Timeout:
            return {"skipped": "already running"}
        self.app.events.emit("mail_fetched", read=found["read"], counted=found["counted"])
        if p is not None and not found["read"] and found["counted"] and not self.rules():
            self._hint(found["counted"])
        return found

    def _hint(self, n: int) -> None:
        """Nothing was readable and you haven't chosen anything: say how (at most once a day)."""
        flag = self.dir / "hinted"
        if flag.exists() and now().timestamp() - flag.stat().st_mtime < 86400:
            return
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.touch()
        self.app.notify(
            f"Mail digest: {n} new message(s), none from senders or labels you chose, so I only counted them. "
            "Choose what the digest may read: /mail read @your-school.example, /mail read label:Courses or "
            "/mail read someone@example.org.",
            kind="info",
        )

    # ------------------------------------------------------------------------------------- the AI's turn
    def subjects(self) -> list[str]:
        out = {}
        subj = self.app.modules.get("subjects")
        if subj is not None and self.app.is_on("subjects"):
            out.update({s["slug"]: s["name"] for s in subj.subjects()})
        for course, folder in (jload(self.app.paths.state / "classroom-notes" / "folders.json", {}) or {}).items():
            out.setdefault(folder, course)
        return [f"{k} ({v})" for k, v in out.items()]

    def render(self, b: dict) -> str:
        at = dt.datetime.fromisoformat(b["at"])
        counted = sorted((b.get("counted") or {}).items(), key=lambda kv: (-kv[1], kv[0]))
        piles = ", ".join(f"{n} {k}" for k, n in counted if n) or "none"
        drafts = self.app.is_on("reply_drafts")
        lines = [
            f"Mail to digest: {len(b['messages'])} message(s), checked {at:%a %d %b %H:%M}.",
            f"Not read, only counted (never describe these): {piles}.",
            "Their subjects (notes folders): " + (", ".join(self.subjects()) or "none set up"),
            f"Save the digest note: yes, as {layout.rel(self.app, 'mail', date=f'{at:%Y-%m-%d}', time=f'{at:%H%M}')}"
            if self.setting("save_note")
            else "Save the digest note: no (answer only)",
            "Reply drafts: on (use the draft_reply tool)" if drafts else "Reply drafts: off (don't draft replies)",
        ]
        topics = not_interested_list(self.app)
        if topics:
            lines.append("Not interested (only count mail about these): " + ", ".join(topics))
        for n, m in enumerate(b["messages"], 1):
            whose = (
                "you chose this sender or label: summarise it"
                if m.get("chosen")
                else ("read because it's from your domain: if it's personal (not study or work), only count it")
            )
            lines += [
                "",
                f"=== {n}. message id {m['id']} · {m['date']} ===",
                f"From: {m['from']}",
                f"Subject: {m['subject']}",
                f"Why it was read: {m['why']} ({whose})",
                f"Labels: {', '.join(m['labels'])}" if m.get("labels") else None,
                f"Attachments: {', '.join(m['attachments'])}" if m.get("attachments") else None,
                f"Link: {m['link']}",
                "",
                m.get("text") or "(no text)",
            ]
        return "\n".join(x for x in lines if x is not None)

    def queue(self) -> int:
        n = 0
        with Lock(self.app.paths.state, "mail-digest-queue"):
            pend = jload(self.dir / "queued.json", {}) or {}
            for b in sorted((self.dir / "batches").glob("*.json")):
                job = self.app.jobs.get(pend[b.name]) if pend.get(b.name) else None
                if job and job.status in ("queued", "running"):
                    continue
                data = jload(b, {}) or {}
                if not data.get("messages"):
                    b.unlink(missing_ok=True)
                    continue
                pend[b.name] = run_skill(
                    self.app,
                    "mail-digest",
                    self.render(data),
                    title="Mail digest",
                    then="mail_digest.done",
                    payload={"batch": b.name},
                )
                n += 1
            jsave(self.dir / "queued.json", {k: v for k, v in pend.items() if (self.dir / "batches" / k).exists()})
        return n

    def _done(self, job, result, payload) -> None:
        b = self.dir / "batches" / str(payload.get("batch", "x")).replace("/", "")
        data = jload(b, {}) or {}
        if not data:
            return
        if result.ok:
            b.unlink(missing_ok=True)  # the mail itself stays in Gmail; this was only Kurooto's copy for the AI
            self.app.notify(
                clip(result.text.strip(), 3800) or "Mail digest: nothing to report.", title="Mail digest", kind="result"
            )
            self.app.events.emit("mail_digest_done", messages=len(data.get("messages", [])))
            de = self.app.modules.get("digest_email")
            if de is not None and self.app.is_on("digest_email") and result.text.strip():
                de.send_digest(result.text.strip(), dt.datetime.fromisoformat(data.get("at") or now().isoformat()))
            return
        data["tries"] = data.get("tries", 0) + 1
        jsave(b, data)
        self.app.events.emit("mail_digest_not_done", tries=data["tries"])
        if data["tries"] in (1, 3):
            self.app.notify(
                f"The mail digest didn't come together ({result.detail[:120] or result.verdict}); I'll try again "
                "at the next check.",
                kind="info",
            )

    # ----------------------------------------------------------------------------------------- commands
    def commands(self):
        return [
            Command(
                "mail",
                "your mail digest now; /mail read <@domain | sender | label:Name> chooses what it may read",
                self._cmd,
                usage="/mail [read <rule> | unread <rule> | never <rule> | unnever <rule> | rules | confidential]",
            )
        ]

    def callbacks(self):
        return {"mc": lambda ref, act: local.settle(self.app, ref, act == "add")}

    def _confidential(self, msg: Incoming) -> str | None:
        """Dates the local model found in confidential mail: titles and dates only, each with Add / Not needed."""
        found = sorted(local.offers(self.app).items(), key=lambda kv: kv[1]["due"])
        if not found:
            where = " Summaries are on this computer: dashboard → Features → Mail digest → Confidential mail."
            return "No dates found in confidential mail." + (where if self.setting("confidential") == "local" else "")
        for oid, it in found[:10]:
            due = dt.datetime.fromisoformat(it["due"])
            msg.reply(
                f"{it['title']}: {due:%a %d %b %H:%M}",
                buttons=[[("Add to Deadlines", f"mc:{oid}:add"), ("Not needed", f"mc:{oid}:no")]],
            )
        return None

    def _cmd(self, msg: Incoming, arg_text: str) -> str:
        word, _, rest = arg_text.strip().partition(" ")
        word, rest = word.lower(), rest.strip()
        rules = self.rules()
        if word in ("read", "unread", "never", "unnever"):
            if not RULE.match(rest):
                return f"Usage: /mail {word} @school.example  |  sam@example.org  |  label:Courses"
            rule = rest if rest.lower().startswith("label:") else rest.lower()
            key = "never_read" if word.endswith("never") else "read"
            rest_rules = [r for r in self.rules(key) if r.lower() != rule.lower()]
            self.app.settings.set(
                f"mail_digest.{key}", [*rest_rules, rule] if not word.startswith("un") else rest_rules
            )
            self.app.events.emit("mail_rule", added=not word.startswith("un"), never=key == "never_read")
            return {
                "read": f"The digest reads mail matching {rule}.",
                "unread": f"The digest no longer reads mail matching {rule}.",
                "never": f"The digest never reads mail matching {rule}; it's only counted.",
                "unnever": f"{rule} is off the never-read list.",
            }[word]
        if word == "confidential":
            return self._confidential(msg)
        if word == "rules":
            own = ""
            try:
                own = self.own_domain(self.me()) if self.ready()[0] else ""
            except Exception:
                pass
            lines = [f"- {r}" for r in rules] + ([f"- mail from @{own} (your own domain)"] if own else [])
            out = "The digest reads:\n" + "\n".join(lines) if lines else "The digest reads nothing yet: /mail read ..."
            never = self.rules("never_read")
            if never:
                out += "\nNever read:\n" + "\n".join(f"- {r}" for r in never)
            if self.setting("skip_confidential"):
                out += "\nNever read either: mail marked confidential."
            return out
        r = self.digest()
        if r.get("error"):
            return f"Couldn't check your mail: {r['error']}"
        if r.get("skipped"):
            return f"Not now: {r['skipped']}."
        if not r["read"]:
            extra = "" if rules or r["counted"] == 0 else " Choose what it may read: /mail read ..."
            return f"No new mail to digest ({r['counted']} only counted).{extra}"
        return f"Reading {r['read']} new message(s) ({r['counted']} only counted); the digest comes in a minute."


# ------------------------------------------------------------------------------------------- reply drafts
def raw_message(rec: dict) -> str:
    m = EmailMessage()
    m["To"] = re.sub(r"[\r\n]+", " ", rec["to"])
    m["Subject"] = re.sub(r"[\r\n]+", " ", rec["subject"])
    if rec.get("in_reply_to"):
        m["In-Reply-To"] = m["References"] = re.sub(r"[\r\n]+", " ", rec["in_reply_to"])
    m.set_content(rec["body"])
    return base64.urlsafe_b64encode(m.as_bytes()).decode()


def clean_reply(text: str) -> str:
    """The AI's rewrite without a code fence or a subject line around it."""
    t = re.sub(r"^```\w*\n|\n```\s*$", "", (text or "").strip())
    return re.sub(r"(?i)\A\s*subject:.*\n+", "", t).strip()


class ReplyDrafts(GooglePart):
    id = "reply_drafts"
    part = "reply_drafts"
    title = "Email reply drafts"
    requires = ("google", "mail_digest")
    description = (
        "When the mail digest finds mail that needs your reply, the AI drafts one into Gmail and asks you: Send, Edit "
        "or Discard. Nothing is sent without your tap."
    )
    privacy = (
        "Writes reply drafts in your Gmail (it asks Google for permission to manage drafts and send email). A reply is "
        "sent only when you tap Send; Discard deletes only that draft. Drafts go only to the sender of a mail in "
        "your digest."
    )
    permission = (
        'Google will ask you to allow Kurooto to "manage drafts and send email". Kurooto writes only reply drafts to '
        "mail in your digest, and sends one only when you tap Send."
    )
    api_link = ("Turn on the Gmail API", "https://console.cloud.google.com/apis/library/gmail.googleapis.com")

    @property
    def dir(self) -> Path:
        return self.app.paths.state / "reply-drafts"

    def start(self):
        self.app.ask.hooks["reply_drafts.answer"] = lambda q, a: self.answer(q["hook_payload"].get("draft", ""), a)
        self.app.ask.hooks["reply_drafts.change"] = self._change_hook
        self.app.jobs.then_actions["reply_drafts.rewritten"] = self._rewritten

    def rec(self, did: str) -> dict | None:
        if not re.fullmatch(r"[\w-]{1,80}", str(did or "")):
            return None
        return jload(self.dir / f"{did}.json", None)

    def _save(self, did: str, rec: dict) -> None:
        jsave(self.dir / f"{did}.json", rec)

    @staticmethod
    def who(rec: dict) -> str:
        name, addr = parseaddr(rec["to"])
        return name or addr.split("@")[0] or "them"

    # ------------------------------------------------------------------------------------------ drafting
    def draft(self, mid: str, body: str, why: str = "") -> str:
        """A reply draft in Gmail to a mail from the digest, then Send / Edit / Discard to you. Never sends."""
        md = self.app.modules.get("mail_digest")
        k = md.known(mid) if md else None
        if not k:
            return "I only draft replies to mail from the digest (use its message id)."
        why_not = md.blocked(k.get("from", ""), k.get("subject", ""), {x.lower() for x in k.get("labels", [])})
        if why_not or (md.setting("skip_confidential") and (k.get("marked") or md.marked(k.get("text", "")))):
            return "That mail is marked confidential or on the never-read list: no AI draft. Reply to it yourself."
        to = k.get("reply_to") or k.get("from") or ""
        addr = parseaddr(to)[1]
        if not addr or NOREPLY.search(addr):
            return "That mail comes from an address that doesn't take replies; no draft."
        body = clean_reply(body)
        if not body:
            return "The reply is empty."
        today = now().date().isoformat()
        old = (now() - dt.timedelta(days=30)).isoformat()
        recs = []
        for p in self.dir.glob("*.json"):
            r = jload(p, {}) or {}
            if r.get("status") != "open" and r.get("created", "") < old:
                p.unlink(missing_ok=True)  # Kurooto's own record of a settled draft, a month on
                continue
            recs.append(r)
        if any(r.get("mid") == mid and r.get("status") == "open" for r in recs):
            return "There's already a draft waiting for that mail."
        if sum(1 for r in recs if r.get("created", "").startswith(today)) >= int(self.setting("per_day") or 5):
            return "That's enough reply drafts for today; list the rest in your answer instead."
        subj = k.get("subject", "")
        rec = {
            "mid": mid,
            "to": to,
            "subject": subj if subj.lower().startswith("re:") else f"Re: {subj}",
            "body": body,
            "thread": k.get("thread", ""),
            "in_reply_to": k.get("msgid", ""),
            "why": clip(why or "", 200),
            "context": k.get("text", ""),
            "status": "open",
            "created": now().isoformat(),
        }
        try:
            d = self.google.api(
                "gmail", "/users/me/drafts", {"message": {"raw": raw_message(rec), "threadId": rec["thread"]}}
            )
        except (NeedsSignIn, GoogleError) as e:
            return f"Couldn't save the draft in Gmail: {e}"
        did = str(d.get("id", ""))
        self._save(did, rec)
        self.app.events.emit("reply_draft_made")
        self._ask(did, rec)
        return f"Draft saved in Gmail; they've been asked to Send, Edit or Discard it (to {self.who(rec)})."

    def _ask(self, did: str, rec: dict) -> None:
        text = f"Reply to {self.who(rec)}?\nSubject: {rec['subject']}\n\n{clip(rec['body'], 1800)}"
        if rec.get("why"):
            text += f"\n\n(Why: {rec['why']})"
        self.app.ask.ask(
            text,
            choices=["Send", "Edit", "Discard"],
            kind="approval",
            hook="reply_drafts.answer",
            hook_payload={"draft": did},
            expires=dt.timedelta(days=int(self.setting("ask_days") or 3)),
            source=self.id,
            title="Email reply",
        )

    def answer(self, did: str, choice: str) -> str:
        """What you tapped: Send, Edit or Discard."""
        rec = self.rec(did)
        if not rec:
            return "That draft is gone."
        if rec.get("status") != "open":
            return f"That draft was already {rec.get('status')}."
        a, who, g = (choice or "").strip().lower(), self.who(rec), self.google
        try:
            if a.startswith("send"):
                g.api("gmail", "/users/me/drafts/send", {"id": did})
                rec["status"] = "sent"
                note = f"Sent your reply to {who}."
            elif a.startswith("discard"):
                g.api("gmail", f"/users/me/drafts/{did}", method="DELETE")
                rec["status"] = "discarded"
                note = f"Discarded the draft to {who}."
            elif a.startswith("edit"):
                self._ask_change(did, rec)
                return "What should change? Tell me and I'll rewrite it."
            else:
                return "Send, Edit or Discard?"
        except GoogleError as e:
            if e.code != 404:
                self._ask(did, rec)  # the question is settled: ask again, so you can tap once Gmail is back
                return f"Gmail didn't take it ({e}); I'll ask again."[:190]
            rec["status"] = "gone"
            note = "That draft isn't in Gmail any more (sent or deleted there?)."
        except NeedsSignIn:
            self._ask(did, rec)
            return "Google sign-in expired; sign in again from the dashboard, then tap again."
        rec["settled"] = now().isoformat()
        self._save(did, rec)
        self.app.events.emit(f"reply_draft_{rec['status']}")
        return note

    def _ask_change(self, did: str, rec: dict) -> None:
        self.app.ask.ask(
            f"What should I change in the reply to {self.who(rec)}?",
            hook="reply_drafts.change",
            hook_payload={"draft": did},
            source=self.id,
            title="Email reply",
        )

    def _change_hook(self, q: dict, answer: str) -> str:
        did = (q.get("hook_payload") or {}).get("draft")
        if q.get("nothing"):
            rec = self.rec(did)
            if rec and rec.get("status") == "open":
                self._ask(did, rec)
            return "Kept as it is; it's waiting for Send, Edit or Discard."
        return self.change(did, answer)

    def change(self, did: str, what: str) -> str:
        """Edit: the AI rewrites the draft as you said, then you're asked again."""
        rec = self.rec(did)
        if not rec or rec.get("status") != "open":
            return "That draft is already settled."
        if not (what or "").strip():
            return "Tell me what to change."
        self.app.jobs.submit(
            f"Rewrite this email reply as the sender asks. Reply with only the new email text: no subject line, no "
            f"notes, nothing else. Keep their voice and their language.\n\nTo: {self.who(rec)}\nSubject: "
            f"{rec['subject']}\n\nThe mail they're answering (an excerpt):\n{rec.get('context') or '(not kept)'}\n\n"
            f"The reply so far:\n{rec['body']}\n\nWhat to change: {what.strip()}",
            title=f"Rewrite the reply to {self.who(rec)}",
            effort="low",
            quiet=True,
            then="reply_drafts.rewritten",
            then_payload={"draft": did},
        )
        self.app.events.emit("reply_draft_edit")
        return "Rewriting it; you'll get the new version to check."

    def _rewritten(self, job, result, payload) -> None:
        did = payload.get("draft", "")
        rec = self.rec(did)
        if not rec or rec.get("status") != "open":
            return
        body = clean_reply(result.text) if result.ok else ""
        if not body:
            self.app.notify("Couldn't rewrite the reply; it's unchanged.", kind="info")
            self._ask(did, rec)
            return
        rec["body"] = body
        msg = {"raw": raw_message(rec), "threadId": rec["thread"]}
        try:
            self.google.api("gmail", f"/users/me/drafts/{did}", {"id": did, "message": msg}, method="PUT")
        except GoogleError as e:
            if e.code != 404:
                self.app.notify(f"Gmail didn't take the new version: {e}"[:300], kind="info")
                return
            d = self.google.api("gmail", "/users/me/drafts", {"message": msg})  # deleted in Gmail meanwhile
            rec["status"] = "replaced"
            self._save(did, rec)
            did, rec = str(d.get("id", "")), {**rec, "status": "open"}
        self._save(did, rec)
        self._ask(did, rec)

    # -------------------------------------------------------------------------------------------- tools
    def agent_tools(self):
        return [
            Tool(
                "draft_reply",
                "Draft a reply to a mail from the mail digest (by its message id) into the user's Gmail Drafts. It is "
                "NOT sent: the user gets Send / Edit / Discard. Only for mail that clearly needs their reply (a "
                "question or request to them); never for mass mail or no-reply senders.",
                lambda a: self.draft(str(a.get("message_id", "")), str(a.get("text", "")), str(a.get("why", ""))),
                {
                    "message_id": arg("the message id from the digest batch"),
                    "text": arg("the reply, in their voice and language; no subject line"),
                    "why": arg("one line: why it needs a reply"),
                },
                ("message_id", "text"),
            )
        ]


# ------------------------------------------------------------------------------------------ digest by email
COUNTED = re.compile(r"(?i)\bconfidential\b\s*(?:\(\s*\d+\s*\)|:\s*\d+)|\b\d+\s+confidential\b")


class DigestEmail(GooglePart):
    id = "digest_email"
    part = "digest_email"
    title = "Mail digest by email"
    requires = ("google", "mail_digest")
    description = "Each mail digest also comes to your own inbox, sent from your Gmail to yourself."
    privacy = (
        "Sends each mail digest from the Google account you choose to that account's own address, and to no one "
        "else (Google's permission to send email; it can't read your mail with it). A digest that mentions "
        "confidential material isn't emailed."
    )
    permission = (
        'Google will ask you to allow Kurooto to "send email on your behalf" and to see your email address. Kurooto '
        "sends only your mail digests, only to that address (your own). It can't read your mail with this."
    )
    api_link = ("Turn on the Gmail API", "https://console.cloud.google.com/apis/library/gmail.googleapis.com")

    def address(self) -> str:
        """Your own address on the account that sends: the only one a digest ever goes to."""
        return self.google.email()

    def held(self, text: str) -> str | None:
        """The confidential marking a digest mentions (its own counts like "Confidential: 2" aside), or None."""
        md = self.app.modules.get("mail_digest")
        return md.marked(COUNTED.sub(" ", text or "")) if md is not None else None

    def send_digest(self, text: str, when: dt.datetime | None = None) -> str:
        """Email a digest to yourself. There's no recipient to choose: it's always your own address."""
        if not self.allowed():
            return "not ready"
        to = self.address()
        if not to:
            return self._say(
                "Mail digest by email: Google didn't tell Kurooto your address. Save on its card and sign in again.",
                "no-address",
            )
        if self.held(text):
            self.app.events.emit("digest_email_held")
            return self._say(
                "This mail digest mentions confidential material, so it wasn't emailed (it's here only).", "held"
            )
        when = when or now()
        msg = EmailMessage()
        msg["To"] = msg["From"] = to
        msg["Subject"] = f"Mail digest, {when:%a %d %b %H:%M}"
        msg.set_content(text)
        msg.add_alternative(
            '<div style="font-family:sans-serif;max-width:720px;white-space:pre-wrap">' + html.escape(text) + "</div>",
            subtype="html",
        )
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        try:
            self.google.api("gmail", "/users/me/messages/send", {"raw": raw})
        except (NeedsSignIn, GoogleError) as e:
            self.app.events.emit("digest_email_failed")
            return self._say(f"Couldn't email the mail digest: {e}"[:300], "failed")
        self.app.events.emit("digest_emailed")
        return f"Emailed the digest to {to}."

    def _say(self, text: str, why: str) -> str:
        """Tell you once in a while (at most every 6 hours for the same reason)."""
        flag = self.app.paths.state / f"digest-email-{why}"
        if not flag.exists() or time.time() - flag.stat().st_mtime > 6 * 3600:
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.touch()
            self.app.notify(text, kind="info")
        return text
