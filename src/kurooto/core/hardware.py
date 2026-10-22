"""Read the machine (OS, CPU, memory, graphics, disk, battery) and pick the settings that suit it.

Profiles:
    light       no usable graphics card, or under 8 GB of memory: no local models, lighter dashboard
    apple       Apple Silicon Mac with 16 GB+ (apple-8: 8 GB, embeddings only)
    small-gpu   NVIDIA card with 4 to 8 GB (e.g. a 4 GB laptop GPU): one small helper model plus embeddings
    big-gpu     NVIDIA card with 8 GB or more (big-gpu-12: 12 GB+, adds a vision model)

Everything here is a recommendation; the user can change any of it in Settings.
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import sys
import tomllib
from dataclasses import asdict, dataclass, field
from importlib import resources
from pathlib import Path

import psutil

from kurooto.core import proc
from kurooto.core.config import register_defaults

GB = 1024**3

register_defaults(
    "hardware",
    {
        "force_profile": "",  # another setup than detected: light, apple-8, apple, small-gpu, big-gpu, big-gpu-12
        "extra_models": [],  # Ollama models of your own to install, e.g. ["gemma4:12b"], past what suits this computer
        "extra_prereqs": [],  # other programs Kurooto should install for you (their ids, e.g. "tesseract")
    },
)


@dataclass
class GPU:
    name: str
    vram_gb: float | None  # None when the OS doesn't say (integrated graphics share main memory)
    vendor: str  # nvidia | apple | amd | intel | other


@dataclass
class Machine:
    os: str  # windows | macos | linux
    os_version: str
    arch: str
    cpu: str
    cores: int
    threads: int
    ram_gb: float
    gpus: list[GPU] = field(default_factory=list)
    disk_free_gb: float = 0.0
    disk_path: str = ""
    battery: bool = False
    on_ac: bool | None = None

    @property
    def nvidia_vram(self) -> float:
        return max((g.vram_gb or 0) for g in self.gpus if g.vendor == "nvidia") if self.nvidia else 0.0

    @property
    def nvidia(self) -> bool:
        return any(g.vendor == "nvidia" for g in self.gpus)

    @property
    def apple_silicon(self) -> bool:
        return self.os == "macos" and self.arch in ("arm64", "aarch64")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Machine:
        d = dict(d)
        d["gpus"] = [GPU(**g) for g in d.get("gpus") or []]
        keep = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in keep})


# ------------------------------------------------------------------------------------------- detection
def _cpu_name() -> str:
    try:
        if sys.platform == "win32":
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        if sys.platform == "darwin":
            r = proc.run(["sysctl", "-n", "machdep.cpu.brand_string"], timeout=5)
            if r.ok and r.out.strip():
                return r.out.strip()
        else:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
                if line.lower().startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or platform.machine()


def _vendor(name: str) -> str:
    n = name.lower()
    for v, keys in (
        ("nvidia", ("nvidia", "geforce", "rtx", "gtx", "quadro")),
        ("amd", ("amd", "radeon")),
        ("intel", ("intel", "iris", "uhd")),
        ("apple", ("apple",)),
    ):
        if any(k in n for k in keys):
            return v
    return "other"


def _nvidia() -> list[GPU]:
    exe = proc.which("nvidia-smi", [Path(r"C:\Windows\System32")] if sys.platform == "win32" else None)
    if not exe:
        return []
    r = proc.run([exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], timeout=15)
    out = []
    if r.ok:
        for line in r.out.splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2 and parts[1].replace(".", "").isdigit():
                out.append(GPU(parts[0], round(float(parts[1]) / 1024, 1), "nvidia"))
    return out


def _windows_gpus() -> list[GPU]:
    ps = "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM | ConvertTo-Json -Compress"
    r = proc.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], timeout=30)
    if not r.ok or not r.out.strip():
        return []
    try:
        data = json.loads(r.out)
    except ValueError:
        return []
    out = []
    for g in data if isinstance(data, list) else [data]:
        name = str(g.get("Name") or "graphics")
        ram = g.get("AdapterRAM")
        # AdapterRAM is a 32-bit field, wrong above 4 GB; trust it only for small values
        vram = round(ram / GB, 1) if isinstance(ram, int) and 0 < ram < 4 * GB else None
        out.append(GPU(name, vram, _vendor(name)))
    return out


def _mac_gpus() -> list[GPU]:
    r = proc.run(["system_profiler", "SPDisplaysDataType", "-json"], timeout=30)
    try:
        items = json.loads(r.out).get("SPDisplaysDataType", []) if r.ok else []
    except ValueError:
        items = []
    out = []
    for g in items:
        name = g.get("sppci_model") or g.get("_name") or "graphics"
        vram = None
        m = re.match(r"(\d+)\s*(GB|MB)", str(g.get("spdisplays_vram") or g.get("spdisplays_vram_shared") or ""))
        if m:
            vram = float(m[1]) / (1 if m[2] == "GB" else 1024)
        out.append(GPU(name, vram, _vendor(name)))
    return out


def _linux_gpus() -> list[GPU]:
    if not shutil.which("lspci"):
        return []
    r = proc.run(["lspci"], timeout=10)
    out = []
    for line in r.out.splitlines() if r.ok else []:
        if re.search(r"VGA compatible|3D controller|Display controller", line):
            name = line.split(":", 2)[-1].strip()
            if _vendor(name) != "nvidia":  # NVIDIA comes from nvidia-smi, with its memory
                out.append(GPU(name, None, _vendor(name)))
    return out


def detect(target: Path | None = None) -> Machine:
    """Read this machine. `target` is where Kurooto will be installed (for the free-space figure)."""
    os_name = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    vm = psutil.virtual_memory()
    gpus = _nvidia()
    if os_name == "windows":
        gpus += [g for g in _windows_gpus() if g.vendor != "nvidia" or not gpus]
    elif os_name == "macos":
        gpus += _mac_gpus()
    else:
        gpus += _linux_gpus()
    target = Path(target or Path.home())
    probe = target
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    free = shutil.disk_usage(probe).free / GB
    bat = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    return Machine(
        os=os_name,
        os_version=platform.mac_ver()[0] if os_name == "macos" else platform.release(),
        arch=platform.machine().lower(),
        cpu=_cpu_name(),
        cores=psutil.cpu_count(logical=False) or 1,
        threads=psutil.cpu_count(logical=True) or 1,
        ram_gb=round(vm.total / GB, 1),
        gpus=gpus,
        disk_free_gb=round(free, 1),
        disk_path=str(probe),
        battery=bat is not None,
        on_ac=None if bat is None else bool(bat.power_plugged),
    )


# --------------------------------------------------------------------------------------------- profiles
def _models() -> dict:
    with resources.files("kurooto.data").joinpath("ollama_models.toml").open("rb") as f:
        return tomllib.load(f)


def profile(m: Machine) -> str:
    if m.ram_gb < 7.5:  # "8 GB" machines report a little under 8
        return "light"
    if m.apple_silicon:
        return "apple" if m.ram_gb >= 15 else "apple-8"
    v = m.nvidia_vram
    if v >= 11.5:
        return "big-gpu-12"
    if v >= 7.5:
        return "big-gpu"
    if v >= 3.5:
        return "small-gpu"
    return "light"


@dataclass
class Recommendation:
    profile: str
    summary: str  # one plain sentence for the wizard
    local_models: list[dict]  # [{key, tag, size_gb, use}]
    embeddings: str  # ollama | gemini | none
    dashboard_fps: int
    reduced_motion: bool
    parallel_jobs: int
    notes: list[str]


PROFILES = ("light", "apple-8", "apple", "small-gpu", "big-gpu", "big-gpu-12")


def registry_size_gb(tag: str, timeout: float = 15.0) -> float | None:
    """The download size of an Ollama model from the registry's manifest (None if it can't be told)."""
    import urllib.request

    name, _, ver = tag.partition(":")
    path = name if "/" in name else f"library/{name}"
    url = f"https://registry.ollama.ai/v2/{path}/manifests/{ver or 'latest'}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:  # noqa: S310 (Ollama's registry)
            data = json.loads(r.read().decode("utf-8"))
        return round(sum(int(layer.get("size", 0)) for layer in data.get("layers", [])) / 1e9, 2) or None
    except (OSError, ValueError, KeyError):
        return None


def extra_models(extra, sizes: dict | None = None) -> list[dict]:
    """Models you added yourself (hardware.extra_models: tags, or {"tag", "size_gb"}), as recommendation rows."""
    out = []
    for e in extra or []:
        tag = str(e.get("tag") if isinstance(e, dict) else e).strip()
        if not tag:
            continue
        size = (e.get("size_gb") if isinstance(e, dict) else None) or (sizes or {}).get(tag)
        out.append(
            {"key": f"extra:{tag}", "tag": tag, "size_gb": float(size or 0), "use": "added by you", "extra": True}
        )
    return out


def limits(m: Machine, models: list[dict], p: str) -> list[str]:
    """What you'd be going past by using these models here, in plain words (never a refusal: it's your computer)."""
    table = _models().get("models") or {}
    warn = []
    v = m.nvidia_vram
    for mod in models:
        need = mod.get("min_vram_gb") or (table.get(mod.get("key")) or {}).get("min_vram_gb") or 0
        if mod.get("extra"):
            size = mod.get("size_gb") or 0
            if m.apple_silicon:
                if size and size > m.ram_gb * 0.6:
                    warn.append(f"{mod['tag']} ({size:g} GB) is large for {m.ram_gb:g} GB of memory.")
            elif size and v and size > v * 0.95:
                warn.append(
                    f"{mod['tag']} ({size:g} GB) is bigger than your {v:g} GB of graphics memory: "
                    "part of it runs on the processor, much slower."
                )
            elif size and not v:
                warn.append(f"{mod['tag']} has no graphics card to run on: it will run on the processor, slowly.")
        elif need and not m.apple_silicon and v < need - 0.5:
            warn.append(
                f"{mod['tag']} wants about {need:g} GB of graphics memory; this computer has {v:g} GB, "
                "so it may run slowly or not fit."
            )
    if p == "light" and any(not x.get("extra") for x in models):
        warn.append("Local models on a computer without a usable graphics card run on the processor: slow, and loud.")
    return warn


def recommend(m: Machine, force: str = "", extra=None, sizes: dict | None = None) -> Recommendation:
    """What suits this machine. `force` (hardware.force_profile) uses another profile's models instead (you know your
    computer better than the detection does), and `extra` adds models of your own; both come with plain warnings
    about what they go past, never a refusal."""
    detected = profile(m)
    p = force if force in PROFILES else detected
    table = _models()
    models = [{"key": k, **table["models"][k]} for k in table["profiles"].get(p, [])]
    models += extra_models(extra, sizes)
    gpu = next((g.name for g in m.gpus if g.vendor == "nvidia"), None) or (m.gpus[0].name if m.gpus else None)
    notes = []
    if p == "light":
        what = "no graphics card Kurooto can use" if not m.nvidia and not m.apple_silicon else "limited memory"
        summary = (
            f"{m.cpu}, {m.ram_gb:g} GB memory, {what}: everything runs on the AI you choose, "
            "nothing heavy on this computer."
        )
    elif p.startswith("apple"):
        summary = f"Apple Silicon ({m.cpu}) with {m.ram_gb:g} GB: small local models run well here."
        if p == "apple-8":
            notes.append("With 8 GB, only the notes index runs locally; answers come from the AI you choose.")
    else:
        summary = f"{gpu} with {m.nvidia_vram:g} GB of graphics memory and {m.ram_gb:g} GB memory."
        if p == "small-gpu":
            notes.append("Models of 7B and up don't fit in 4 GB; they would run slowly and heat the laptop.")
    if m.battery and m.on_ac is False:
        notes.append("You're on battery: heavy work waits for the charger.")
    if p != detected:
        notes.insert(0, f'You chose the "{p}" setup (this computer was detected as "{detected}").')
    notes += limits(m, models, p)
    return Recommendation(
        profile=p,
        summary=summary,
        local_models=models,
        embeddings="ollama" if any(x["key"] == "embed" for x in models) else "gemini",
        dashboard_fps=30 if p == "light" else 60,
        reduced_motion=p == "light",
        parallel_jobs=1 if p in ("light", "apple-8") else 2,
        notes=notes,
    )


def current(app) -> dict:
    """{"machine", "recommendation", "at"} for this computer with your overrides (hardware.force_profile and
    hardware.extra_models) applied; the machine is read once and kept (state/hardware.json), the recommendation is
    worked out again each time, so a change takes effect at once."""
    import time

    from kurooto.core.state import jload, jsave

    f = app.paths.state / "hardware.json"
    cached = jload(f, None)
    if cached and cached.get("machine"):
        m = Machine.from_dict(cached["machine"])
        at = cached.get("at", time.time())
    else:
        m, at = detect(app.paths.app), time.time()
    extra = app.settings.get("hardware.extra_models") or []
    sizes = dict(jload(app.paths.state / "model-sizes.json", {}) or {})
    for e in extra:
        tag = str(e.get("tag") if isinstance(e, dict) else e)
        if tag and tag not in sizes and not (isinstance(e, dict) and e.get("size_gb")):
            got = registry_size_gb(tag)
            if got:
                sizes[tag] = got
    if sizes:
        jsave(app.paths.state / "model-sizes.json", sizes)
    rec = asdict(recommend(m, str(app.settings.get("hardware.force_profile") or ""), extra, sizes))
    out = {"machine": m.to_dict(), "recommendation": rec, "at": at}
    jsave(f, out)
    return out


if __name__ == "__main__":  # python -m kurooto.core.hardware
    mach = detect()
    print(json.dumps({"machine": mach.to_dict(), "recommendation": asdict(recommend(mach))}, indent=1))
