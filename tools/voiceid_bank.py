#!/usr/bin/env python3
"""Build Voice ID's impostor set for one speaker model (a dev tool; Kurooto never imports it).

    uv run --with onnxruntime --with kaldi-native-fbank --with soundfile --with numpy \\
        python tools/voiceid_bank.py --librispeech /path/to/librispeech --model <the .onnx> \\
        --name campplus-en --out src/kurooto/data/voiceid/

--librispeech: a folder holding LibriSpeech's dev-clean, test-clean, dev-other and test-other (146 speakers, CC BY 4.0,
https://www.openslr.org/12), as extracted (LibriSpeech/<split>/<speaker>/<chapter>/*.flac). The dev and test splits
keep the set out of any training data (LibriSpeech isn't in CAM++'s VoxCeleb2 training).
--cv: optionally, a Common Voice English folder (CC0: validated.tsv and clips/); up to 150 more speakers whose accent
says "India and South Asia".

Per speaker: 4 utterances of 4 s or more, spread over chapters; for each, three vectors: the whole utterance, a 3 s
and a 1.5 s crop from its middle (the short crops give the impostor scores for short turns). About 146 x 4 x 3 = 1,750
rows. Only vectors ship: no audio, speaker ids or transcripts. The file is modules/voice/speakerid.py's bank format
(one JSON header line with the model's sha256, then float16 rows), impostors-<name>.bin. Download the data to a scratch
folder on a big disk, never to ~, and delete it afterwards.

--channel phone (0.9.2, Voice ID per microphone): the same utterances first passed through a simulated phone channel,
written as impostors-<name>-phone.bin. Voice ID calibrates a print built on another microphone (a phone's, through an
add-on) against it, so strangers are scored as they'd sound through that kind of microphone. Simulated here, offline,
from the dev/test audio only: never a real microphone, never a synthetic (TTS) voice. Three channels in turn, one per
utterance (phone_channel): "mic" (a phone microphone's response: a high-pass at 150 Hz, a presence lift at 2-4 kHz, a
roll-off above 6.5 kHz, then automatic gain and soft compression), "call" (mic, then band-limited to 300-3400 Hz and
8-bit mu-law, the narrowband voice-call path) and "far" (mic at arm's length: a short room tail and a noise floor 30 dB
under the speech)."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from kurooto.modules.voice import speakerid as sid  # noqa: E402

SPLITS = ("dev-clean", "test-clean", "dev-other", "test-other")
PER_SPEAKER = 4
MIN_S = 4.0


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def load16k(path: Path):
    import numpy as np
    import soundfile as sf

    x, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != 16000:
        n = int(len(x) * 16000 / sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype("float32")
    return (np.clip(x, -1, 1) * 32767).astype("<i2")


CHANNELS = ("mic", "call", "far")


def _shape(x, gains):
    """x (float32, 16 kHz) through a gain curve over frequency: gains(freqs in Hz) -> linear gains."""
    import numpy as np

    n = len(x)
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / 16000)
    return np.fft.irfft(spec * gains(f), n).astype("float32")


def phone_channel(x16, which: str, seed: int):
    """int16 16 kHz -> int16 16 kHz through a simulated phone channel (module docstring). Deterministic per seed."""
    import numpy as np

    rng = np.random.default_rng(seed)
    x = x16.astype("float32") / 32768.0

    def mic_eq(f):
        hp = 1 / np.sqrt(1 + (150 / np.maximum(f, 1.0)) ** 4)  # 2nd-order high-pass at 150 Hz
        lift = 1 + 0.41 * np.exp(-(((f - 3000) / 900) ** 2))  # about +3 dB around 2-4 kHz
        lp = 1 / np.sqrt(1 + (f / 6500) ** 8)  # roll-off above 6.5 kHz
        return hp * lift * lp

    x = _shape(x, mic_eq)
    if which == "far":
        n = int(0.25 * 16000)  # a short room tail: decaying noise, 250 ms
        tail = rng.standard_normal(n).astype("float32") * np.exp(-np.arange(n) / (0.05 * 16000)).astype("float32")
        tail[0] = 1.0
        x = np.convolve(x, tail * 0.3, mode="full")[: len(x)].astype("float32")
    rms = float(np.sqrt(np.mean(x**2))) or 1e-6  # automatic gain to about -20 dBFS, then soft compression
    x = x * (0.1 / rms)
    x = np.tanh(2.0 * x) / 2.0
    if which == "far":
        x = x + rng.standard_normal(len(x)).astype("float32") * (0.1 * 10 ** (-30 / 20))
    if which == "call":
        x = _shape(x, lambda f: ((f >= 300) & (f <= 3400)).astype("float32"))
        mu = 255.0  # 8-bit mu-law, there and back
        y = np.sign(x) * np.log1p(mu * np.minimum(np.abs(x), 1.0)) / np.log1p(mu)
        y = np.round((y + 1) * 127.5) / 127.5 - 1
        x = np.sign(y) * ((1 + mu) ** np.abs(y) - 1) / mu
    return (np.clip(x, -1, 1) * 32767).astype("<i2")


def middle(x, seconds: float):
    n = int(seconds * 16000)
    if len(x) <= n:
        return x
    a = (len(x) - n) // 2
    return x[a : a + n]


def librispeech(root: Path) -> dict[str, list[Path]]:
    out: dict[str, list[Path]] = {}
    for split in SPLITS:
        base = next((p for p in (root / "LibriSpeech" / split, root / split) if p.is_dir()), None)
        if base is None:
            print(f"  (no {split} under {root})")
            continue
        for spk in sorted(p for p in base.iterdir() if p.is_dir()):
            files = sorted(spk.rglob("*.flac"))
            by_ch: dict[str, list[Path]] = {}
            for f in files:
                by_ch.setdefault(f.parent.name, []).append(f)
            picked = []
            while len(picked) < PER_SPEAKER * 3 and any(by_ch.values()):  # round-robin over chapters
                for ch in sorted(by_ch):
                    if by_ch[ch]:
                        picked.append(by_ch[ch].pop(0))
            out[f"ls-{split}-{spk.name}"] = picked
    return out


def common_voice(root: Path, limit: int = 150) -> dict[str, list[Path]]:
    tsv = root / "validated.tsv"
    if not tsv.is_file():
        return {}
    by: dict[str, list[Path]] = {}
    with open(tsv, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if "india" not in (row.get("accents") or row.get("accent") or "").lower():
                continue
            c = row.get("client_id") or ""
            if c and len(by.setdefault(c, [])) < PER_SPEAKER * 3:
                by[c].append(root / "clips" / row["path"])
    return {f"cv-{i}": v for i, (_k, v) in enumerate(sorted(by.items())[:limit])}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--librispeech", type=Path, required=True)
    ap.add_argument("--cv", type=Path, default=None)
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--name", required=True, help="campplus-en or campplus-multi (the file's name)")
    ap.add_argument("--out", type=Path, default=ROOT / "src" / "kurooto" / "data" / "voiceid")
    ap.add_argument("--channel", choices=("plain", "phone"), default="plain", help="phone: a simulated phone channel")
    a = ap.parse_args()

    emb = sid.Embedder(a.model)
    speakers = librispeech(a.librispeech)
    if a.cv:
        speakers.update(common_voice(a.cv))
    rows, kinds, n_spk = [], [], 0
    for i, (_spk, files) in enumerate(sorted(speakers.items()), 1):
        took = 0
        for f in files:
            if took >= PER_SPEAKER:
                break
            try:
                x = load16k(f)
            except Exception as e:
                print(f"  skipped a file: {type(e).__name__}")
                continue
            if len(x) < MIN_S * 16000:
                continue
            if a.channel == "phone":
                x = phone_channel(x, CHANNELS[len(rows) // 3 % len(CHANNELS)], len(rows))
            for kind, piece in ((sid.KIND_FULL, x), (sid.KIND_3S, middle(x, 3.0)), (sid.KIND_15, middle(x, 1.5))):
                rows.append(emb.embed(piece.tobytes()))
                kinds.append(kind)
            took += 1
        n_spk += took > 0
        print(f"[{i}/{len(speakers)}] {took} utterances")
    if not rows:
        print("No speech found.", file=sys.stderr)
        return 1
    a.out.mkdir(parents=True, exist_ok=True)
    dest = a.out / f"impostors-{a.name}{'-phone' if a.channel == 'phone' else ''}.bin"
    source = "LibriSpeech dev/test (CC BY 4.0)" + (
        " and Common Voice English, India and South Asia (CC0)" if a.cv else ""
    )
    meta = {"model_sha256": sha256(a.model), "speakers": n_spk, "source": source}
    if a.channel == "phone":
        meta["channel"] = "phone (simulated: " + ", ".join(CHANNELS) + ")"
    sid.write_bank(dest, rows, kinds, meta)
    print(f"{dest}: {len(rows)} rows from {n_spk} speakers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
