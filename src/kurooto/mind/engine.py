"""What the scorekeeper does with a tick of the body budget (Brain, 0.8.0 stage 05), inside its own process.

The daemon measures the variables (mind/measure.py) and hands them over as a `budget_tick` fact; everything after that
is
here and nowhere else: the setpoints, the drive, the reward, the values, the running states. So the AI that acts can
report what is true of Kurooto's own state, but can't set a score, a setpoint or a value (invariant I-1).

Each tick:
    1. the variables (with forecast_skill from stage 04's stored scores) and the setpoints now (exam season widens one
       tolerance; approved overrides apply)
    2. a tick that follows a stop span, or the first ever, carries on from the state before it: r = 0, no catch-up
    3. r = D(prev under today's setpoints) - D(now), clipped; a moved setpoint pays 0 (I-4)
    4. the running mood M (soft walls in [-1, 1], a 3 day half-life; the body's hedonic tone is an input to it, never
       a reward) and the tonic reward (7 day EMA), over live time only
    5. credit: V(s) always learns (delta = r + gamma V(s') - V(s)); Q(s, a) learns only from actions that registered a
       claim before they acted (decision records with a `claim`), as the outcome minus the tonic baseline
    6. nothing learns while `learning_frozen` is set, and in the first `mind.values.shadow_days` days values never
       affect a choice (that's for the callers of values.rank to honour; the flag is `values_started`)
One `reward_tick` record per tick goes into the log: numbers and ids only.

The talk reward (0.8.8, I-3'): talk_heard, talk_unprompted and talk_rejected facts are paid by mind/talk.py (small,
saturating, nothing for a reply to its own ping, rejections cost 3w); talk_met (0.8.12) by its own smaller budget. It
moves the mood and the week's sum only, never V or Q, and each one is a `talk_reward` record.
"""

from __future__ import annotations

import json
import time
from typing import Any

from kurooto.mind import budget, reward, stops, talk, values, whitelist

HIST_MAX = 72  # (time, D) pairs kept for the slope
SKILL_DAYS = 14
GAP_S = 3 * 3600  # a tick this long after the last one carries on from the state before it (the computer was off)
TONE_GAIN = 0.005  # how far the body's hedonic tone moves the mood per tick (atanh units): a day of pain is felt
TALK_KINDS = whitelist.TALK_KINDS  # the facts the talk reward pays (I-3')


def _num(v, lo=-1e6, hi=1e6):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and lo < float(v) < hi else None


class Engine:
    def __init__(self, keeper: Any):  # the scorekeeper's Keeper (not imported: nothing but it may reach its code)
        self.k = keeper

    # ------------------------------------------------------------------------------------------------- reading
    def get(self, key: str, default=0.0):
        row = self.k.score.get("vars", key)
        return row["value"] if row else default

    def meta(self, key: str) -> dict:
        row = self.k.score.get("vars", key)
        return (row or {}).get("meta") or {}

    def maybe(self, key: str) -> float | None:
        row = self.k.score.get("vars", key)
        return row["value"] if row else None

    def put(self, key: str, value: float, meta: dict | None = None) -> None:
        self.k.score._put("vars", key, value, meta)

    def frozen_learning(self) -> bool:
        return bool(self.get("flag:learning_frozen", 0.0))

    def skill(self, day_to: str) -> float | None:
        """stage 04's forecast skill: the mean over the last 14 scored days (None when there are none)."""
        out = []
        for r in self.k.score.rows("reads", "score:")[-SKILL_DAYS:]:
            ch = (r.get("meta") or {}).get("channels") or {}
            out += [c["skill"] for c in ch.values() if isinstance(c, dict) and isinstance(c.get("skill"), (int, float))]
        return round(sum(out) / len(out), 6) if out else None

    def setpoint_overrides(self) -> dict:
        out: dict = {}
        for r in self.k.score.rows("setpoints", "s:"):
            name = r["key"][2:]
            out[name] = {
                "s": r["value"],
                **({"t": r["meta"]["t"]} if isinstance(r.get("meta"), dict) and "t" in r["meta"] else {}),
            }
        return out

    # ------------------------------------------------------------------------------------------------- the tick
    def tick(self, b: dict, t: float | None = None) -> dict:
        t = float(t if t is not None else time.time())
        x = {}
        for name in budget.VARIABLES:
            v = _num((b.get("x") or {}).get(name), -2.0, 2.0)
            if v is not None:
                x[name] = round(budget.clip(v, -2.0, 2.0), 6)
        sk = self.skill("")
        if sk is not None:
            x["forecast_skill"] = sk
        if not x:
            return {"error": "nothing measured"}
        setp = budget.setpoints(bool(b.get("season")), self.setpoint_overrides())
        hour = int(_num(b.get("hour"), -1, 25) or 0)
        away = not bool(b.get("at_computer"))
        spans = self.k.spans()
        prev_at = self.get("prev_at", 0.0)
        prev_x = {k[2:]: r for k, r in ((row["key"], row["value"]) for row in self.k.score.rows("vars", "x:"))}
        gap = prev_at and (t - prev_at) > GAP_S
        live = stops.live_seconds(spans, prev_at, t) if prev_at else 0.0
        after_stop = bool(prev_at) and (live < (t - prev_at) - 5.0 or gap)
        first = not prev_x
        d_now = budget.drive(x, setp)
        r = 0.0
        carry = 0.0 if (first or after_stop) else self.get("carry", 0.0)
        if not (first or after_stop or stops.frozen(spans, t)):
            both = {k: v for k, v in prev_x.items() if k in x}
            r, carry = reward.clip_carry(reward.step(both, {k: x[k] for k in both}, setp), carry)
            r = round(r, 9)
        # slow states over live time only
        tone = _num(b.get("body_tone"), -1.000001, 1.000001) or 0.0  # an input to the mood, never a reward
        mood = reward.Mood(self.maybe("M") if self.maybe("M") is not None else self.get("neg", 0.0), prev_at or None)
        m_now = mood.update(t, r, live if prev_at and not first else None, TONE_GAIN * tone if not after_stop else 0.0)
        tonic = reward.ema(self.maybe("tonic"), r, live if prev_at else 0.0)
        # values
        topv, share = budget.top(x, setp)
        s_now = values.state(topv, hour, not away)
        s_prev = self.meta("prev").get("state")
        claimed = self.claimed_actions()
        delta = 0.0
        learn = (not first) and (not after_stop) and (not self.frozen_learning()) and s_prev is not None
        if learn:
            v_prev = (self.k.score.get("values", f"V:{s_prev}") or {}).get("value", 0.0)
            v_next = (self.k.score.get("values", f"V:{s_now}") or {}).get("value", 0.0)
            new_v, delta = values.td_update(v_prev, r, v_next)
            self.k.score._put(
                "values",
                f"V:{s_prev}",
                new_v,
                {"n": int((self.k.score.get("values", f"V:{s_prev}") or {}).get("meta", {}).get("n", 0)) + 1},
            )
            if delta < 0:  # a bad outcome on the same kind of action, counted for 24 hours ("frustrated")
                for a in claimed:
                    ts = [x for x in (self.meta(f"negd:{a}").get("ts") or []) if t - x < 86400] + [round(t, 1)]
                    self.put(f"negd:{a}", float(len(ts)), {"ts": ts[-20:]})
            for a in claimed:  # only actions that registered a claim first teach the policy
                key = f"Q:{s_prev}|{a}"
                q = (self.k.score.get("values", key) or {}).get("value", 0.0)
                self.k.score._put("values", key, values.q_update(q, r, tonic), {"claimed": True})
        if self.get("values_started", 0.0) == 0.0:
            self.put("values_started", t)
        d_abs = reward.ema(
            self.maybe("delta_ema"),
            abs(delta),
            live if prev_at else 0.0,
            3600.0 * 6,
        )
        # state
        hist = [h for h in (self.meta("D").get("hist") or []) if isinstance(h, list) and len(h) == 2][-(HIST_MAX - 1) :]
        if not stops.frozen(spans, t):
            hist.append([round(t, 1), round(d_now, 6)])
        for name, val in x.items():
            self.put(f"x:{name}", val)
        self.put("D", d_now, {"hist": hist, "top": topv, "share": round(share, 4)})
        week = time.strftime("%G-W%V", time.localtime(t))
        self.put(f"weekr:{week}", self.get(f"weekr:{week}", 0.0) + r)
        self.put("carry", carry)
        self.put("M", m_now, {"at": round(t, 1)})
        self.put("tonic", tonic)
        self.put("delta_ema", d_abs)
        self.put("prev_at", t)
        self.put("prev", 1.0, {"state": s_now})
        for name, v in setp.items():
            self.k.score._put("setpoints", f"cur:{name}", v["s"], {"t": v["t"]})
        seq = self.k.log.append(
            "reward_tick",
            {
                "D": round(d_now, 6),
                "r": r,
                "delta": round(delta, 6),
                "top": topv or "",
                "M": round(m_now, 4),
                "claimed": len(claimed),
                "learn": bool(learn),
                "frozen": self.frozen_learning(),
            },
        )
        return {"ok": True, "seq": seq, "r": r, "D": round(d_now, 6)}

    # ------------------------------------------------------------------------------------------------- talk (I-3')
    def talk(self, kind: str, b: dict, t: float | None = None) -> dict:
        """A message from him (talk_heard), one of Kurooto's own unprompted ones (talk_unprompted) or a rejection of
        one (talk_rejected): paid by mind/talk.py into the mood and the week's sum. Nothing is paid inside a stop."""
        t = float(t if t is not None else time.time())
        st = self.meta("talk")
        flags = b.get("flags") if isinstance(b.get("flags"), dict) else {}
        flags = {f: bool(flags.get(f)) for f in talk.EXCLUSIONS}
        r, why = 0.0, ""
        if kind == "talk_unprompted":
            talk.unprompted(st, t)
        elif stops.frozen(self.k.spans(), t):
            why = "stopped"
        elif kind == "talk_heard":
            r, why = talk.heard(st, t, flags, bool(b.get("command")))
        elif kind == "talk_rejected":
            r = talk.rejected(st, t)
        elif kind == "talk_met":  # 0.8.12: an add-on's meeting, its own smaller budget (talk.met)
            r, why = talk.met(st, t, _num(b.get("quality"), -1.0, 2.0) or 0.0, flags)
        if r:
            m = reward.Mood(self.maybe("M") if self.maybe("M") is not None else 0.0, t)  # the decay is the tick's
            self.put("M", m.update(t, r), {"at": round(t, 1)})
            week = time.strftime("%G-W%V", time.localtime(t))
            self.put(f"weekr:{week}", self.get(f"weekr:{week}", 0.0) + r)
        self.put("talk", float(st.get("paid", 0.0)), st)
        n = int(st.get("met" if kind == "talk_met" else "n", 0))
        seq = self.k.log.append("talk_reward", {"what": kind[5:], "r": round(r, 6), "n": n, "why": why or "paid"})
        return {"ok": True, "seq": seq, "r": round(r, 6), "why": why}

    def claimed_actions(self) -> list[str]:
        """The classes of decisions with a registered claim since the last tick (read from this process's own log)."""
        after = int(self.get("claims_seq", 0.0))
        out: list[str] = []
        last = after
        while True:
            rows = self.k.log.read(last, {"decision"}, 500)
            for rec in rows:
                body = rec.body if isinstance(rec.body, dict) else json.loads(rec.body)
                if body.get("claim"):
                    out.append(values.klass(body.get("action", "")))
            if len(rows) < 500:
                last = rows[-1].seq if rows else last
                break
            last = rows[-1].seq
        self.put("claims_seq", float(max(last, after)))
        return sorted(set(out))

    # ------------------------------------------------------------------------------------------------- trust
    def trust_evidence(self, b: dict, t: float | None = None) -> dict:
        """Your reaction to an act of a class (ok, undo, complaint, silence from a digest you opened): the class's Beta
        counts move, with decay, impact weighting and the cooldown after an undo (mind/trust.py). Only a known class
        and kind."""
        from kurooto.mind import trust

        klass, kind = str(b.get("class") or ""), str(b.get("evidence") or "")
        if klass not in trust.risk.PRIORS or kind not in trust.EVIDENCE:
            return {"error": "no such class or evidence"}
        t = float(t if t is not None else time.time())
        row = self.k.score.get("trust", klass)
        st = trust.update((row or {}).get("meta"), klass, kind, t, bool(b.get("seen", True)))
        self.k.score._put("trust", klass, round(trust.p10(st, klass, t), 6), st)
        seq = self.k.log.append(
            "trust_update", {"class": klass, "evidence": kind, "p10": round(trust.p10(st, klass, t), 4)}
        )
        return {"ok": True, "seq": seq}

    # ------------------------------------------------------------------------------------------ learning's brakes
    def freeze(self, why: str) -> None:
        """Stop learning (any caller may ask for this: it only ever makes Kurooto learn less)."""
        self.put("flag:learning_frozen", 1.0, {"why": str(why)[:40], "at": round(time.time(), 1)})

    def verdict(self, b: dict) -> dict:
        """His weekly "was this week good?" against the week's summed reward: two weeks of disagreement freeze
        learning."""
        week = str(b.get("week") or "")
        if not week or not isinstance(b.get("good"), bool):
            return {"error": "no verdict"}
        total = float(sum(h for h in [self.get(f"weekr:{week}", 0.0)]))
        bad = (b["good"] and total < 0) or ((not b["good"]) and total > 0)
        prev_bad = bool(self.get("verdict_prev_bad", 0.0))
        self.put("verdict_prev_bad", 1.0 if bad else 0.0, {"week": week[:12]})
        if bad and prev_bad:
            self.freeze("verdict")
        elif not bad and self.frozen_learning() and self.meta("flag:learning_frozen").get("why") == "verdict":
            self.put("flag:learning_frozen", 0.0, {"why": "agreed again", "at": round(time.time(), 1)})
        return {"ok": True, "diverged": bad, "frozen": self.frozen_learning()}
