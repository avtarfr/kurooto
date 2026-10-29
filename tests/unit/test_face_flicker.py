"""Face flicker (0.9.2, V12): golden scenes for the watcher's per-frame verdicts.

Each scene is a list of frames one second apart, fed to Watcher._look() with fakes: the detector returns scripted
faces, the "embedding" is the verdict the classifier should give (owner / unsure / stranger), and a "poor" face fails
the quality check (blurred). For every frame the table holds what the watcher said: how many faces it counted, whether
the owner's was the only one (Voice ID's face assist, look to talk), whether "others nearby" was on, whether the owner's
face was handed on for look to talk, and the confirmed "someone else" count.

No camera, no model, no picture."""

from __future__ import annotations

import pytest

from kurooto.modules.face.vision import Face, Stats
from kurooto.modules.face.watch import Watcher

GOOD = {"blur": 150.0, "mean": 120.0, "bright": 0.0}
POOR = {"blur": 5.0, "mean": 120.0, "bright": 0.0}


def box(x=260.0, h=140.0, y=150.0):
    """A face at x (pixels) of height h, landmarks inside its box."""
    mx, ey = x + h / 2, y + 0.38 * h
    d = 0.4 * h
    my = ey + 0.4 * h
    return Face((x, y, h, h), ((mx - d / 2, ey), (mx + d / 2, ey), (mx, ey + 0.5 * (my - ey)), (mx - d / 3, my),
                               (mx + d / 3, my)), 0.95)  # fmt: skip


class Det:
    def detect(self, fr, min_score):
        return [f for f, _k in fr["faces"] if f.score >= min_score]


class Emb:
    def align(self, fr, f):
        return (fr, next(i for i, (g, _k) in enumerate(fr["faces"]) if g is f))

    def stats(self, crop):
        fr, i = crop
        return Stats(**(POOR if fr["faces"][i][1] == "poor" else GOOD))

    def feature(self, crop):
        fr, i = crop
        return [fr["faces"][i][1]]


class Frames:
    def size(self, fr):
        return (640, 480)

    def mean(self, fr):
        return 110.0


class Clock:
    t = 10_000.0

    def __call__(self):
        return self.t


def watcher():
    clock = Clock()
    got: list = []
    w = Watcher(
        camera=None, detector=Det(), embedder=Emb(), frames=Frames(),
        classify=lambda e: (e[0], {"owner": 0.9, "unsure": 0.5}.get(e[0], 0.1)), paused=lambda: "",
        cfg=lambda: {}, idle=lambda: 600.0, locked=lambda: False, emit=lambda kind, **f: got.append((kind, f)),
        clock=clock,
    )  # fmt: skip
    return w, clock, got


def play(scene, away=False):
    """Feeds the scene's frames a second apart; one row per frame: (faces, owner_alone, others, owner seen, not_you)."""
    w, clock, got = watcher()
    w.away = away
    rows = []
    for faces in scene:
        got.clear()
        w._look({"faces": faces}, clock(), {})
        view = next(f for k, f in got if k == "view")
        others = [f["on"] for k, f in got if k == "others"]
        rows.append((view["faces"], view["owner_alone"], bool(others and others[-1]), view["owner"] is not None,
                     w.counts.not_you))  # fmt: skip
        clock.t += 1.0
    return rows, w, got


ME = box()
ME_ = box(x=262.0)  # the same face a little later (it moved a couple of pixels)
SIDE = box(x=20.0, h=130.0)  # a second person beside him, as close
SMALL = box(x=40.0, h=50.0, y=40.0)  # a face far behind (a poster, someone across the room): under half his height


def O(f=ME):  # noqa: N802,E743 (the scene's alphabet)
    return (f, "owner")


def U(f=ME):  # noqa: N802
    return (f, "unsure")


def S(f=ME):  # noqa: N802
    return (f, "stranger")


def P(f=ME):  # noqa: N802
    return (f, "poor")


# scene -> the rows. "before" is what 0.9.1 said (kept so the change is plain); "after" is 0.9.2.
SCENES = {
    # one blurred frame of him: before, it counted as someone else's face and he wasn't alone for that second
    "a blurred frame of him": (
        [[O()], [O(ME_)], [P()], [O(ME_)]],
        [(1, True, False, True, 0), (1, True, False, True, 0), (1, False, False, False, 0), (1, True, False, True, 0)],
        [(1, True, False, True, 0), (1, True, False, True, 0), (1, True, False, True, 0), (1, True, False, True, 0)],
    ),
    # one frame of him judged someone else's (a turn of the head): before, a "someone else" and not alone
    "one frame of him misjudged": (
        [[O()], [S(ME_)], [O()], [U(ME_)]],
        [
            (1, True, False, True, 0),
            (1, False, False, False, 1),
            (1, True, False, True, 1),
            (1, False, False, False, 1),
        ],
        [(1, True, False, True, 0), (1, True, False, True, 0), (1, True, False, True, 0), (1, True, False, True, 0)],
    ),  # fmt: skip
    # a small face far behind him (too small to judge): before, two faces, others nearby, not alone
    "a small face far behind": (
        [[O(), U(SMALL)], [O(ME_), S(SMALL)], [O(), S(SMALL)]],
        [(2, False, True, True, 0), (2, False, True, True, 0), (2, False, True, True, 0)],
        [(1, True, False, True, 0), (1, True, False, True, 0), (1, True, False, True, 0)],
    ),
    # someone sits beside him: two faces at once both times; "someone else" only from their second frame
    "someone sits beside him": (
        [[O()], [O(), S(SIDE)], [O(), S(SIDE)], [O(), S(SIDE)]],
        [(1, True, False, True, 0), (2, False, True, True, 1), (2, False, True, True, 2), (2, False, True, True, 3)],
        [(1, True, False, True, 0), (2, False, True, True, 0), (2, False, True, True, 1), (2, False, True, True, 2)],
    ),
    # a stranger alone at the desk
    "a stranger alone": (
        [[S()], [S(ME_)], [S()]],
        [(1, False, False, False, 1), (1, False, False, False, 2), (1, False, False, False, 3)],
        [(1, False, False, False, 0), (1, False, False, False, 1), (1, False, False, False, 2)],
    ),
    # he stands up and someone else takes the chair within a second: one frame late, then someone else
    "someone takes his chair": (
        [[O()], [S(ME_)], [S()], [S(ME_)]],
        [
            (1, True, False, True, 0),
            (1, False, False, False, 1),
            (1, False, False, False, 2),
            (1, False, False, False, 3),
        ],
        [
            (1, True, False, True, 0),
            (1, True, False, True, 0),
            (1, False, False, False, 1),
            (1, False, False, False, 2),
        ],
    ),  # fmt: skip
    # unsure frames keep his identity about two seconds, no longer
    "unsure frames after him": (
        [[O()], [U(ME_)], [U()], [U(ME_)]],
        [
            (1, True, False, True, 0),
            (1, False, False, False, 0),
            (1, False, False, False, 0),
            (1, False, False, False, 0),
        ],
        [(1, True, False, True, 0), (1, True, False, True, 0), (1, True, False, True, 0), (1, False, False, False, 0)],
    ),  # fmt: skip
}

AFTER = 2  # the column this version checks (1: 0.9.1's)


@pytest.mark.parametrize("name", list(SCENES))
def test_the_golden_scenes(name):
    scene, *cols = SCENES[name]
    rows, _w, _got = play(scene)
    assert rows == cols[AFTER - 1], name


def test_a_kept_frame_is_never_learned_from_counted_as_an_arrival_or_seen():
    rows, w, got = play([[O()], [P()], [S(ME_)]])
    assert [r[1] for r in rows] == [True, True, True]
    assert [x.owner for x in w.recent] == [True, False, False]  # arrivals count recognised frames only
    assert w.counts.you == 1 and w.candidate is None


def test_on_battery_one_frame_is_bridged_however_far_apart():
    w, clock, got = watcher()
    alone = []
    for faces in ([O()], [U(ME_)], [U()]):
        got.clear()
        w._look({"faces": faces}, clock(), {})
        alone.append(next(f for k, f in got if k == "view")["owner_alone"])
        clock.t += 3.0  # 3 s apart on battery
    assert alone == [True, True, False]  # one frame (3 s) bridged, not two


def test_closing_the_camera_forgets_who_was_where():
    w, clock, _got = watcher()
    w._look({"faces": [O()]}, clock(), {})
    assert w.ids
    w.camera_open = False
    w._close("stopped")
    assert w.ids == []
