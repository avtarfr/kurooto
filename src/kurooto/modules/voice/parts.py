"""What Voice needs on this computer, fetched only when you set it up (Features → Voice → Set up): Python packages
into Kurooto's own folder (never the system's, never Kurooto's own environment), and model files. Sizes are what
they take on disk, roughly.

    packages (installed by uv, or pip, into <app>/voice/py-<python version>; licences as published)
        audio    sounddevice (MIT; PortAudio, MIT) and numpy (BSD): playing and recording sound     ~0.06 GB
        kokoro   kokoro-onnx (MIT) with onnxruntime (MIT); its phonemes come from espeak-ng, which
                 phonemizer-fork and espeakng-loader bring (GPL-3.0)                                ~0.2 GB
        piper    piper-tts (GPL-3.0 since 1.3; MIT before)                                          ~0.05 GB
        listen   faster-whisper (MIT) with CTranslate2 (MIT), onnxruntime (MIT)                      ~0.45 GB
        wake     only with a wake word model of your own (voice.listen.wake_word): openwakeword 0.6.0
                 (Apache-2.0), installed without its tflite-runtime dependency (no wheels for Python 3.12;
                 the ONNX models are used instead), with scipy, scikit-learn, tqdm, requests          ~0.2 GB
        voiceid  only with Voice ID (voice.speaker_id.on): kaldi-native-fbank (Apache-2.0), the feature
                 extractor the speaker model was converted with                                       ~0.001 GB
    models (into <app>/voice/models)
        kokoro       Kokoro-82M v1.0, ONNX (Apache-2.0) and its voices                              337 MB
        piper        the en_US "lessac" medium voice (MIT voice card; trained on a public dataset)   63 MB
        vad          Silero VAD v5 (MIT)                                                             2.3 MB
        whisper-*    faster-whisper's CTranslate2 conversions of OpenAI Whisper (MIT): tiny 75 MB,
                     base 145 MB, small 484 MB
        wake-common  openWakeWord's feature models (melspectrogram, and the speech embedding derived from
                     Google's Apache-2.0 model), which any openWakeWord model needs; only with your own
                     wake word model                                                             2.4 MB
        voiceid-campplus-en     Voice ID's speaker model: CAM++ trained on VoxCeleb (3D-Speaker, Apache-2.0),
                                ONNX conversion by k2-fsa/sherpa-onnx (Apache-2.0)                    28 MB
        voiceid-campplus-multi  the same for English and other languages (CAM++ zh+en, Apache-2.0)    27 MB
    openWakeWord's ready-made wake words ("hey jarvis" ...) are never fetched: they're CC BY-NC-SA 4.0. By default
    Kurooto wakes on its name, heard by the transcriber (names.py).

Files with a pinned sha256 (Voice ID's models) are checked while they download: a mismatch keeps nothing. They can also
be installed from a file already on this computer (Parts.add_file: `kurooto voice parts add FILE`, the Your voice
page), for a machine without internet; so can a package's wheel (.whl), with the usual installer and no index.

Downloads go through core/egress.py (github.com, whose release files come from release-assets.githubusercontent.com,
and huggingface.co); the packages are handed to uv (or pip), which
fetches them from PyPI. Each file lands as <name>.part and is renamed when complete, so a broken download is fetched
again next time.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from kurooto.core import egress, proc
from kurooto.core.state import jload

Progress = Callable[[str], None]
OWW = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1"
HF = "https://huggingface.co"
STT_MODELS = {"tiny": 75, "base": 145, "small": 484}  # MB
KOKORO_VOICES = (
    "af_heart",
    "af_bella",
    "af_nicole",
    "af_sarah",
    "am_michael",
    "am_adam",
    "bf_emma",
    "bf_isabella",
    "bm_george",
    "bm_lewis",
)


@dataclass(frozen=True)
class Package:
    key: str
    specs: tuple[str, ...]
    module: str  # what's importable once it's in (a folder or a .py in the target)
    size_gb: float
    what: str
    no_deps: tuple[str, ...] = ()  # installed after, without their declared dependencies


@dataclass(frozen=True)
class ModelFile:
    name: str
    url: str
    mb: float
    sha256: str = ""  # pinned: checked while it downloads (and for a file installed from disk); "" not pinned (Voice ID's
    # and Face presence's models are)


SV = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models"  # (sic: the tag's spelling)
VOICEID_MODELS = {  # voice.speaker_id.model -> (part key, file); the speaker models (Voice ID, speakerid.py)
    "campplus-en": ("voiceid-campplus-en", "voiceid/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx"),
    "campplus-multi": (
        "voiceid-campplus-multi",
        "voiceid/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx",
    ),
}


PACKAGES = {
    p.key: p
    for p in (
        Package("audio", ("sounddevice>=0.5", "numpy>=1.26"), "sounddevice", 0.06, "playing and recording sound"),
        Package("kokoro", ("kokoro-onnx>=0.4",), "kokoro_onnx", 0.2, "the Kokoro speech engine"),
        Package("piper", ("piper-tts>=1.3",), "piper", 0.05, "the Piper speech engine"),
        Package(
            "listen", ("onnxruntime>=1.18", "faster-whisper>=1.1"), "faster_whisper", 0.45, "writing out speech here"
        ),
        Package(
            "wake",
            ("scipy>=1.11", "scikit-learn>=1.3", "tqdm>=4.66", "requests>=2.31"),
            "openwakeword",
            0.2,
            "the wake word",
            no_deps=("openwakeword==0.6.0",),
        ),
        Package(
            "voiceid", ("kaldi-native-fbank>=1.22,<2",), "kaldi_native_fbank", 0.001, "telling your voice from others'"
        ),
    )
}


def models() -> dict[str, list[ModelFile]]:
    kokoro = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
    piper = f"{HF}/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium"
    out = {
        "kokoro": [
            ModelFile("kokoro-v1.0.onnx", f"{kokoro}/kokoro-v1.0.onnx", 310),
            ModelFile("voices-v1.0.bin", f"{kokoro}/voices-v1.0.bin", 27),
        ],
        "piper": [
            ModelFile("en_US-lessac-medium.onnx", f"{piper}/en_US-lessac-medium.onnx", 63),
            ModelFile("en_US-lessac-medium.onnx.json", f"{piper}/en_US-lessac-medium.onnx.json", 0.01),
        ],
        "vad": [
            ModelFile(
                "silero_vad.onnx",
                "https://github.com/snakers4/silero-vad/raw/v5.1.2/src/silero_vad/data/silero_vad.onnx",
                2.3,
            )
        ],
        "wake-common": [
            ModelFile("melspectrogram.onnx", f"{OWW}/melspectrogram.onnx", 1.1),
            ModelFile("embedding_model.onnx", f"{OWW}/embedding_model.onnx", 1.3),
        ],
    }
    out["voiceid-campplus-en"] = [
        ModelFile(
            VOICEID_MODELS["campplus-en"][1],
            f"{SV}/3dspeaker_speech_campplus_sv_en_voxceleb_16k.onnx",
            28.2,
            "357a834f702b80161e5b981182c038e18553c1f2ca752ed6cec2052365d4129b",
        )
    ]
    out["voiceid-campplus-multi"] = [
        ModelFile(
            VOICEID_MODELS["campplus-multi"][1],
            f"{SV}/3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx",
            27.0,
            "aa3cfc16963a10586a9393f5035d6d6b57e98d358b347f80c2a30bf4f00ceba2",
        )
    ]
    for size, mb in STT_MODELS.items():
        base = f"{HF}/Systran/faster-whisper-{size}/resolve/main"
        out[f"whisper-{size}"] = [
            ModelFile(f"whisper-{size}/model.bin", f"{base}/model.bin", mb),
            ModelFile(f"whisper-{size}/config.json", f"{base}/config.json", 0.01),
            ModelFile(f"whisper-{size}/tokenizer.json", f"{base}/tokenizer.json", 2.2),
            ModelFile(f"whisper-{size}/vocabulary.txt", f"{base}/vocabulary.txt", 0.5),
        ]
    return out


class Parts:
    """Voice's parts by default; another feature (Face presence) passes its own packages, model table, models folder
    and name, and shares the packages' folder (one numpy)."""

    def __init__(self, root: Path, app_dir: Path, packages=None, table=None, models_dir=None, feature: str = "Voice"):
        self.root = Path(root)
        self.app_dir = Path(app_dir)
        self.py = self.root / f"py-{sys.version_info.major}.{sys.version_info.minor}"
        self.models_dir = Path(models_dir) if models_dir else self.root / "models"
        self.table = models() if table is None else table
        self.packages = PACKAGES if packages is None else packages
        self.feature = feature

    # -------------------------------------------------------------------------------------------- checking
    def has_package(self, key: str) -> bool:
        m = self.packages[key].module
        return (self.py / m).is_dir() or (self.py / f"{m}.py").is_file()

    def has_model(self, key: str) -> bool:
        return all((self.models_dir / f.name).is_file() for f in self.table.get(key, []))

    def path(self, name: str) -> Path:
        return self.models_dir / name

    def missing(self, keys: list[str]) -> list[str]:
        """The parts of `keys` ("pkg:listen", "model:vad") not on this computer yet."""
        out = []
        for k in keys:
            kind, _, name = k.partition(":")
            if (kind == "pkg" and not self.has_package(name)) or (kind == "model" and not self.has_model(name)):
                out.append(k)
        return out

    def size_gb(self, keys: list[str]) -> float:
        total = 0.0
        for k in keys:
            kind, _, name = k.partition(":")
            if kind == "pkg":
                total += self.packages[name].size_gb
            else:
                total += sum(f.mb for f in self.table.get(name, [])) / 1024
        return round(total, 2)

    def importable(self) -> None:
        """Make the installed packages importable (after Kurooto's own, so they never replace its modules)."""
        p = str(self.py)
        if self.py.is_dir() and p not in sys.path:
            sys.path.append(p)

    # ------------------------------------------------------------------------------------------ installing
    def installer(self) -> list[str] | None:
        """uv (the one Kurooto was installed with, else on PATH) or this Python's pip: the command, without args."""
        info = jload(self.app_dir / "install.json", {}) or {}
        uv = info.get("uv") if info.get("uv") and Path(info["uv"]).exists() else shutil.which("uv")
        if uv:
            return [uv, "pip", "install", "--python", sys.executable]
        if proc.run([sys.executable, "-m", "pip", "--version"], timeout=30).ok:
            return [sys.executable, "-m", "pip", "install", "--disable-pip-version-check"]
        return None

    def install_package(self, key: str, progress: Progress) -> tuple[bool, str]:
        pkg = self.packages[key]
        cmd = self.installer()
        if cmd is None:
            return False, "neither uv nor pip is available to install Python packages"
        progress(f"Installing {pkg.what} ({', '.join(pkg.specs + pkg.no_deps)}, about {pkg.size_gb:g} GB)…")
        egress.handed("uv" if "uv" in Path(cmd[0]).name else "pip", self.feature)
        self.py.mkdir(parents=True, exist_ok=True)
        res = proc.run([*cmd, "--target", str(self.py), *pkg.specs], timeout=1800)
        if res.ok and pkg.no_deps:
            res = proc.run([*cmd, "--no-deps", "--target", str(self.py), *pkg.no_deps], timeout=900)
        if not res.ok or not self.has_package(key):
            return False, f"Installing {pkg.what} failed: {(res.err or res.out).strip()[-300:]}"
        return True, f"{pkg.what}: installed"

    def download_model(self, key: str, progress: Progress) -> tuple[bool, str]:
        for f in self.table[key]:
            dest = self.models_dir / f.name
            if dest.is_file():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_name(dest.name + ".part")
            progress(f"Downloading {f.name} ({f.mb:g} MB)…")
            try:
                digest = hashlib.sha256()
                with egress.urlopen(f.url, self.feature, timeout=60) as r, open(part, "wb") as out:
                    total = int(r.headers.get("Content-Length") or 0)
                    done, last = 0, -1
                    while chunk := r.read(1 << 20):
                        out.write(chunk)
                        digest.update(chunk)
                        done += len(chunk)
                        pct = int(done * 100 / total) if total else -1
                        if total and pct // 25 != last:
                            last = pct // 25
                            progress(f"{f.name}: {pct}%")
                if f.sha256 and digest.hexdigest() != f.sha256:  # (voice id) a damaged or changed download
                    part.unlink(missing_ok=True)
                    what = Path(f.name).name
                    return False, f"{what} didn't match its checksum (a damaged or changed download); nothing was kept"
                os.replace(part, dest)
            except Exception as e:
                part.unlink(missing_ok=True)
                return False, f"Couldn't download {f.name}: {type(e).__name__}: {e}"[:300]
        return True, f"{key}: ready"

    def install(
        self, keys: list[str], progress: Progress, free_gb: Callable[[], float] | None = None
    ) -> tuple[bool, str]:
        need = self.missing(keys)
        if not need:
            return True, f"Everything {self.feature} needs is here."
        gb = self.size_gb(need)
        if free_gb is not None:
            free = free_gb()
            if free - gb < 2:
                return (
                    False,
                    f"Not enough space: {self.feature} needs about {gb:g} GB and {free:g} GB is free "
                    "(2 GB kept spare).",
                )
        progress(f"{self.feature} needs {len(need)} part{'s' if len(need) != 1 else ''}, about {gb:g} GB in all.")
        for i, k in enumerate(need, 1):
            kind, _, name = k.partition(":")
            progress(f"[{i}/{len(need)}] {k}")
            ok, msg = self.install_package(name, progress) if kind == "pkg" else self.download_model(name, progress)
            progress(("✓ " if ok else "✗ ") + msg)
            if not ok:
                return False, msg
        self.importable()
        return True, f"{self.feature} is set up."

    # ---------------------------------------------------------------------------------- from a file (offline)
    def add_file(self, path: str | Path, progress: Progress = lambda _m: None) -> tuple[bool, str]:
        """Install one part from a file already on this computer (a machine without internet). A model file only when
        its name matches a part with a pinned sha256 and its hash matches; a wheel (.whl) of a package Voice uses,
        with the usual installer and no index (other wheels in the same folder, numpy's or onnxruntime's, are found
        too). Nothing is uploaded or fetched."""
        f = Path(str(path)).expanduser()
        if not f.is_file():
            return False, f"{f}: no such file"
        if f.suffix == ".whl":
            return self._add_wheel(f, progress)
        entry = next((m for files in self.table.values() for m in files if Path(m.name).name == f.name), None)
        if entry is None:
            return False, f"{f.name} isn't a part Voice uses"
        if not entry.sha256:
            return False, f"{f.name}: this part has no checksum pinned yet; download it instead"
        progress(f"Checking {f.name}…")
        digest = hashlib.sha256()
        with open(f, "rb") as src:
            while chunk := src.read(1 << 20):
                digest.update(chunk)
        if digest.hexdigest() != entry.sha256:
            return False, f"{f.name} didn't match its checksum (a damaged or different file); nothing was kept"
        dest = self.models_dir / entry.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        try:
            shutil.copyfile(f, part)
            os.replace(part, dest)
        except OSError as e:
            part.unlink(missing_ok=True)
            return False, f"Couldn't copy {f.name}: {type(e).__name__}"
        return True, f"{f.name}: installed from the file"

    def _add_wheel(self, f: Path, progress: Progress) -> tuple[bool, str]:
        dist = re.sub(r"[-_.]+", "-", f.name.split("-", 1)[0]).lower()
        pkg = next(
            (
                p
                for p in PACKAGES.values()
                for spec in p.specs + p.no_deps
                if re.sub(r"[-_.]+", "-", re.split(r"[<>=!~\[ ]", spec, maxsplit=1)[0]).lower() == dist
            ),
            None,
        )
        if pkg is None:
            return False, f"{f.name} isn't a package Voice uses"
        cmd = self.installer()
        if cmd is None:
            return False, "neither uv nor pip is available to install Python packages"
        progress(f"Installing {f.name} from its file…")
        self.py.mkdir(parents=True, exist_ok=True)
        args = [*cmd, "--no-index", "--find-links", str(f.parent), "--target", str(self.py), str(f)]
        res = proc.run(args, timeout=900)
        if not res.ok:
            return False, f"Installing {f.name} failed: {(res.err or res.out).strip()[-300:]}"
        self.importable()
        return True, f"{f.name}: installed from the file"

    def install_from(self, folder: Path, keys: list[str], progress: Progress) -> tuple[bool, str]:
        """For a computer without internet: model files found by name in `folder` are copied in when their checksum
        matches (or they have none), and packages are installed from the wheels there (uv or pip, --no-index). Then
        what's still missing is said."""
        folder = Path(folder).expanduser()
        if not folder.is_dir():
            return False, f"There's no folder at {folder}."
        for k in keys:
            kind, _, name = k.partition(":")
            if kind == "model":
                for f in self.table.get(name, []):
                    dest = self.models_dir / f.name
                    if dest.is_file():
                        continue
                    src = folder / Path(f.name).name
                    if not src.is_file():
                        progress(f"✗ {f.name}: not in the folder")
                        continue
                    if f.sha256 and _sha256(src) != f.sha256:
                        progress(f"✗ {f.name}: the file didn't match its checksum")
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    part = dest.with_name(dest.name + ".part")
                    shutil.copyfile(src, part)
                    os.replace(part, dest)
                    progress(f"✓ {f.name}: copied")
            elif kind == "pkg" and not self.has_package(name):
                pkg, cmd = self.packages[name], self.installer()
                if cmd is None:
                    progress("✗ neither uv nor pip is available to install Python packages")
                    continue
                self.py.mkdir(parents=True, exist_ok=True)
                res = proc.run(
                    [*cmd, "--no-index", "--find-links", str(folder), "--target", str(self.py), *pkg.specs],
                    timeout=1800,
                )
                progress(("✓ " if res.ok and self.has_package(name) else "✗ ") + f"{pkg.what}")
        missing = self.missing(keys)
        if missing:
            return False, f"Still missing: {', '.join(missing)}."
        self.importable()
        return True, f"{self.feature} is set up from {folder}."


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()
