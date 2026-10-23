"""This computer's vitals, for the dashboard's STATUS board and `kurooto top`: the processor (total, each core, its
speed, load, temperature and fans), memory and swap (used, cached, available), the graphics card (load, its memory,
temperature and power), the network (the main connection's down and up rates and totals), disks (how full, and how
fast they're read and written), the battery, and the busiest processes, Kurooto's own marked. Each reading keeps a
short history (newest last) for the graphs.

psutil only, on Windows, macOS and Linux. What a computer can't tell is None or left out, never an error: macOS and
Windows usually have no temperatures or fans; live graphics-card figures come from NVIDIA's nvidia-smi (any OS) or
AMD's driver files (Linux), and a laptop's sleeping NVIDIA card isn't woken to ask (that would cost battery).
Nothing is read until someone looks (an open dashboard, `kurooto top`)."""

from __future__ import annotations

import os
import sys
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path

import psutil

from kurooto.core import proc
from kurooto.core.state import jload

LINUX = sys.platform.startswith("linux")
SKIP_FS = ("squashfs", "tmpfs", "devtmpfs", "overlay", "proc", "sysfs", "autofs", "efivarfs", "fuse.portal")
SKIP_NIC = ("lo", "veth", "docker", "br-", "virbr", "vmnet", "vboxnet", "utun", "awdl", "llw", "anpi", "gif", "stf")
CPU_SENSORS = ("k10temp", "coretemp", "zenpower", "cpu_thermal", "cpu-thermal", "acpitz")
DISK_SENSORS = ("nvme", "drivetemp")
MIB = 1024**2


def _num(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _read(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


class _Cache:
    """Slow readings (sensors, the graphics card, disks) at most every `ttl` seconds; a failing one keeps its last
    value."""

    def __init__(self):
        self.store: dict[str, tuple[float, object]] = {}

    def get(self, key: str, ttl: float, fn: Callable[[], object], force: bool = False):
        at, value = self.store.get(key, (0.0, None))
        if force or time.monotonic() - at >= ttl or not at:
            try:
                value = fn()
            except Exception:  # a broken sensor mustn't take the board down
                pass
            self.store[key] = (time.monotonic(), value)
        return value


def nvidia_asleep() -> bool:
    """Linux laptops put an unused NVIDIA card to sleep, and nvidia-smi would wake it: True while it sleeps."""
    if not LINUX:
        return False
    try:
        for d in Path("/sys/bus/pci/devices").iterdir():
            if _read(d / "vendor") == "0x10de" and (_read(d / "class") or "").startswith("0x03"):
                return _read(d / "power" / "runtime_status") in ("suspended", "suspending")
    except OSError:
        pass
    return False


def nvidia() -> dict | None:
    """The first NVIDIA card's load, memory, temperature and power, or None."""
    exe = proc.which("nvidia-smi")
    if not exe:
        return None
    if nvidia_asleep():
        return {"asleep": True}
    fields = "name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit"
    r = proc.run([exe, f"--query-gpu={fields}", "--format=csv,noheader,nounits"], timeout=4)
    if not r.ok or not r.out.strip():
        return None
    f = [x.strip() for x in r.out.splitlines()[0].split(",")]
    if len(f) < 7:
        return None
    util, used, total = _num(f[1]), _num(f[2]), _num(f[3])
    if util is None or total is None:
        return None
    return {
        "name": f[0],
        "util": util / 100,
        "mem_used": (used or 0) * MIB,
        "mem_total": total * MIB,
        "temp": _num(f[4]),
        "watts": _num(f[5]),
        "watts_max": _num(f[6]),
    }


def amdgpu() -> dict | None:
    """An AMD card's figures from its driver's files (Linux), unless it's asleep."""
    if not LINUX:
        return None
    for card in sorted(Path("/sys/class/drm").glob("card[0-9]")):
        dev = card / "device"
        if _read(dev / "vendor") != "0x1002" or _read(dev / "gpu_busy_percent") is None:
            continue
        if _read(dev / "power" / "runtime_status") in ("suspended", "suspending"):
            return {"asleep": True}
        out = {
            "name": "AMD graphics",
            "util": (_num(_read(dev / "gpu_busy_percent")) or 0) / 100,
            "mem_used": _num(_read(dev / "mem_info_vram_used")) or 0,
            "mem_total": _num(_read(dev / "mem_info_vram_total")) or 0,
            "temp": None,
            "watts": None,
            "watts_max": None,
        }
        for hw in (dev / "hwmon").glob("hwmon*"):
            t, w = _num(_read(hw / "temp1_input")), _num(_read(hw / "power1_average"))
            out["temp"] = t / 1000 if t else None
            out["watts"] = w / 1e6 if w else None
        return out
    return None


def mains_online() -> bool | None:
    """Linux: whether the charger is in, from the power supply files, when psutil can't tell."""
    if not LINUX:
        return None
    for d in Path("/sys/class/power_supply").glob("*"):
        if _read(d / "type") == "Mains":
            v = _read(d / "online")
            if v in ("0", "1"):
                return v == "1"
    return None


def battery_watts() -> float | None:
    """Linux: how much the battery is giving or taking right now, in watts."""
    if not LINUX:
        return None
    for d in Path("/sys/class/power_supply").glob("BAT*"):
        p = _num(_read(d / "power_now"))
        if p is None:
            c, v = _num(_read(d / "current_now")), _num(_read(d / "voltage_now"))
            p = c * v / 1e6 if c is not None and v is not None else None
        if p:
            return p / 1e6
    return None


def nic_wanted(name: str) -> bool:
    low = name.lower()
    return not (low.startswith(SKIP_NIC) or "loopback" in low or "pseudo" in low)


def _busy(t) -> tuple[float, float]:
    """(busy, all) seconds from one core's cpu_times: idle and iowait are idle; guest time is already in user."""
    d = t._asdict()
    idle = d.get("idle", 0.0) + d.get("iowait", 0.0)
    total = sum(d.values()) - d.get("guest", 0.0) - d.get("guest_nice", 0.0)
    return total - idle, total


class Sampler:
    """Read the computer with sample(); each call adds to the histories (keep `history` readings)."""

    def __init__(self, hardware_file: Path | None = None, history: int = 120):
        self.hardware_file = hardware_file
        self.n = history
        self.cache = _Cache()
        self.hist: dict[str, deque] = {
            k: deque(maxlen=history) for k in ("cpu", "mem", "swap", "gpu", "vram", "rx", "tx", "read", "write")
        }
        self.core_hist: list[deque] = []
        self._net: tuple[float, dict] | None = None
        self._io: tuple[float, int, int] | None = None
        self._dev: str | None = None
        # processor use is measured here, from the cores' own counters, over at least a second: psutil.cpu_percent()
        # measures since whichever caller asked last, so two readers a moment apart got windows of milliseconds
        self._times: tuple[float, list] | None = None
        self._cores: list[float] = []
        self._procs: tuple[float, dict] | None = None  # when, pid -> (create_time, cpu seconds) for the process list
        self._share: dict[int, float] = {}
        self._core_use()

    # ------------------------------------------------------------------------------------------- pieces
    def _hardware(self) -> dict:
        if not self.hardware_file:
            return {}
        return self.cache.get("hw", 60, lambda: (jload(self.hardware_file, {}) or {}).get("machine") or {}) or {}

    def _sensors(self) -> tuple[dict, list[int]]:
        temps: dict[str, int] = {}
        fans: list[int] = []
        try:
            st = psutil.sensors_temperatures() or {}
        except (AttributeError, OSError):
            st = {}
        for key, names in (("cpu", CPU_SENSORS), ("disk", DISK_SENSORS)):
            for name in names:
                if st.get(name) and st[name][0].current:
                    temps[key] = round(st[name][0].current)
                    break
        try:
            sf = psutil.sensors_fans() or {}
        except (AttributeError, OSError):
            sf = {}
        if len(sf) > 1:
            sf.pop("acpi_fan", None)  # the firmware's summary of fans the laptop's own driver lists one by one
        for entries in sf.values():
            fans += [int(e.current) for e in entries if e.current and e.current > 0]
        return temps, fans[:4]

    def _freq(self) -> dict | None:
        try:
            f = psutil.cpu_freq()
        except (AttributeError, OSError, NotImplementedError, RuntimeError):
            return None
        if not f or not f.current:
            return None
        return {"cur": round(f.current), "max": round(f.max) if f.max else None}

    def _gpu(self) -> dict | None:
        return nvidia() or amdgpu()

    def _disks(self) -> list[dict]:
        disks, seen = [], set()
        try:
            parts = psutil.disk_partitions(all=False)
        except OSError:
            parts = []
        for part in parts:
            if part.fstype in SKIP_FS or part.device in seen or "/snap/" in part.mountpoint or "cdrom" in part.opts:
                continue
            try:
                u = psutil.disk_usage(part.mountpoint)
            except (OSError, PermissionError):
                continue
            if u.total < 1024**3 or (u.total, u.free) in seen:  # one container's volumes (APFS, btrfs) show once
                continue
            seen.add(part.device)
            seen.add((u.total, u.free))
            disks.append(
                {"mount": part.mountpoint, "used": u.used, "free": u.free, "total": u.total, "pct": u.percent / 100}
            )
        return disks[:6]

    def _network(self) -> dict:
        try:
            per = psutil.net_io_counters(pernic=True) or {}
        except (OSError, RuntimeError):
            per = {}
        stats = self.cache.get("nicstats", 30, psutil.net_if_stats) or {}
        now = time.monotonic()
        rates: dict[str, tuple[float, float]] = {}
        if self._net:
            span = max(0.1, now - self._net[0])
            for name, c in per.items():
                prev = self._net[1].get(name)
                if prev:
                    rates[name] = (max(0, c.bytes_recv - prev[0]) / span, max(0, c.bytes_sent - prev[1]) / span)
        self._net = (now, {n: (c.bytes_recv, c.bytes_sent) for n, c in per.items()})
        names = [n for n in per if nic_wanted(n) and (n not in stats or stats[n].isup)]
        if not names:
            return {"dev": None, "rx": 0.0, "tx": 0.0, "rx_total": 0, "tx_total": 0, "all_rx": 0.0, "all_tx": 0.0}
        dev = self._dev if self._dev in names else max(names, key=lambda n: per[n].bytes_recv + per[n].bytes_sent)
        busy = max(names, key=lambda n: sum(rates.get(n, (0, 0))))
        if busy != dev and sum(rates.get(busy, (0, 0))) > max(2048, 4 * sum(rates.get(dev, (0, 0)))):
            dev = busy  # another connection carries the traffic now (say, Wi-Fi to cable)
        self._dev = dev
        rx, tx = rates.get(dev, (0.0, 0.0))
        return {
            "dev": dev,
            "rx": rx,
            "tx": tx,
            "rx_total": per[dev].bytes_recv,
            "tx_total": per[dev].bytes_sent,
            "all_rx": sum(rates.get(n, (0, 0))[0] for n in names),
            "all_tx": sum(rates.get(n, (0, 0))[1] for n in names),
        }

    def _diskio(self) -> dict | None:
        try:
            c = psutil.disk_io_counters()
        except (OSError, RuntimeError, ValueError):
            c = None
        if c is None:
            return None
        now = time.monotonic()
        prev, self._io = self._io, (now, c.read_bytes, c.write_bytes)
        if not prev:
            return {"read": 0.0, "write": 0.0}
        span = max(0.1, now - prev[0])
        return {"read": max(0, c.read_bytes - prev[1]) / span, "write": max(0, c.write_bytes - prev[2]) / span}

    def _battery(self) -> dict | None:
        try:
            b = psutil.sensors_battery()
        except Exception:
            b = None
        if b is None:
            return None
        ac = b.power_plugged if b.power_plugged is not None else mains_online()
        secs = b.secsleft if isinstance(b.secsleft, (int, float)) and 0 < b.secsleft < 10**6 else None
        return {
            "pct": round(b.percent, 1),
            "ac": bool(ac) if ac is not None else None,
            "secs": secs,
            "watts": self.cache.get("batw", 5, battery_watts),
        }

    def _core_use(self, window: float = 1.0) -> list[float]:
        """Each core's use (0..1) over the last `window` seconds or more, the same for every reader in between."""
        now = time.monotonic()
        if self._times and now - self._times[0] < window and self._cores:
            return self._cores
        try:
            times = psutil.cpu_times(percpu=True)
        except (OSError, RuntimeError):
            return self._cores
        if self._times and len(self._times[1]) == len(times):
            use = []
            for a, b in zip(self._times[1], times, strict=True):
                busy_a, all_a = _busy(a)
                busy_b, all_b = _busy(b)
                d = all_b - all_a
                use.append(min(1.0, max(0.0, (busy_b - busy_a) / d)) if d > 0 else 0.0)
            self._cores = use
        elif not self._cores:
            self._cores = [0.0] * len(times)  # the first reading only sets the baseline
        self._times = (now, times)
        return self._cores

    # ---------------------------------------------------------------------------------------- the reading
    def sample(self, force: bool = False) -> dict:
        cores = list(self._core_use())
        cpu = sum(cores) / max(1, len(cores))
        vm, sw = psutil.virtual_memory(), psutil.swap_memory()
        try:
            load = list(os.getloadavg()) if hasattr(os, "getloadavg") else None
        except OSError:
            load = None
        temps, fans = self.cache.get("sensors", 5, self._sensors, force) or ({}, [])
        gpu = self.cache.get("gpu", 3, self._gpu, force)
        net = self._network()
        io = self._diskio()
        hw = self._hardware()
        cached = getattr(vm, "cached", 0) + getattr(vm, "buffers", 0)
        h = self.hist
        h["cpu"].append(round(cpu, 3))
        h["mem"].append(round(vm.percent / 100, 3))
        h["swap"].append(round(sw.percent / 100, 3))
        live = gpu if gpu and not gpu.get("asleep") else None
        h["gpu"].append(round(live["util"], 3) if live else 0.0)
        h["vram"].append(round(live["mem_used"] / live["mem_total"], 3) if live and live["mem_total"] else 0.0)
        h["rx"].append(round(net["rx"]))
        h["tx"].append(round(net["tx"]))
        h["read"].append(round(io["read"]) if io else 0)
        h["write"].append(round(io["write"]) if io else 0)
        if len(self.core_hist) != len(cores):
            self.core_hist = [deque(maxlen=self.n) for _ in cores]
        for d, v in zip(self.core_hist, cores, strict=True):
            d.append(round(v, 3))
        if live and live.get("temp") is not None:
            temps = {**temps, "gpu": round(live["temp"])}
        return {
            "cpu": cpu,
            "cores": cores,
            "threads": len(cores),
            "phys": psutil.cpu_count(logical=False),
            "cpu_name": hw.get("cpu"),
            "freq": self.cache.get("freq", 3, self._freq, force),
            "load": load,
            "temps": temps,
            "fans": fans,
            "mem": {
                "total": vm.total,
                "used": vm.total - vm.available,
                "available": vm.available,
                "cached": cached,
                "free": vm.free,
                "pct": vm.percent / 100,
            },
            "swap": {"total": sw.total, "used": sw.used, "pct": sw.percent / 100} if sw.total else None,
            "gpu": gpu,
            "gpus": [{"name": g.get("name", "graphics"), "vram_gb": g.get("vram_gb")} for g in hw.get("gpus") or []],
            "net": net,
            "disks": self.cache.get("disks", 30, self._disks, force) or [],
            "io": io,
            "battery": self._battery(),
            "uptime": time.time() - psutil.boot_time(),
            "hist": {k: list(v) for k, v in h.items()},
            "core_hist": [list(d) for d in self.core_hist],
        }

    # -------------------------------------------------------------------------------------------- processes
    def processes(self, own: Callable[[int], str | None] | None = None, n: int = 30) -> list[dict]:
        """The busiest `n` processes by processor and the biggest `n` by memory (one list, busiest first): pid,
        name, cpu (its share of the whole machine, 0..1, the same scale as the total: 1.0 = every core busy),
        mem (bytes), threads, and `own` (a label) for Kurooto's own.

        Processor use is each process's own cpu_times over at least two seconds, the same for every reader in that
        time. psutil's cpu_percent measured since whichever reader asked last, so short windows turned a single 10 ms
        clock tick into 0.8% and an idle process never read 0."""
        rows = []
        total = psutil.virtual_memory().total or 1
        now = time.monotonic()
        fresh = self._procs is None or now - self._procs[0] >= 2.0
        seen: dict[int, tuple[float, float]] = {}
        ncpu = psutil.cpu_count() or 1
        for p in psutil.process_iter(["name", "memory_info", "num_threads", "cpu_times", "create_time"]):
            if p.pid == 0:  # Windows' idle process counts the idle time of every core
                continue
            if fresh:
                ct = p.info.get("cpu_times")
                if ct is not None:
                    seen[p.pid] = (p.info.get("create_time") or 0.0, (ct.user or 0.0) + (ct.system or 0.0))
                    before = self._procs[1].get(p.pid) if self._procs else None
                    if before and before[0] == seen[p.pid][0]:
                        dt = now - self._procs[0]
                        self._share[p.pid] = max(0.0, (seen[p.pid][1] - before[1]) / (dt * ncpu)) if dt > 0 else 0.0
                    else:
                        self._share[p.pid] = 0.0  # new since the last reading: measured from the next one
            cpu = self._share.get(p.pid, 0.0)
            mi = p.info.get("memory_info")
            mem = getattr(mi, "rss", 0) or 0
            rows.append(
                {
                    "pid": p.pid,
                    "name": (p.info.get("name") or "?")[:40],
                    "cpu": round(cpu, 4),
                    "mem": mem,
                    "mem_pct": round(mem / total, 4),
                    "threads": p.info.get("num_threads"),
                    "own": own(p.pid) if own else None,
                }
            )
        if fresh:
            self._procs = (now, seen)
            self._share = {pid: v for pid, v in self._share.items() if pid in seen}
        by_cpu = sorted(rows, key=lambda r: (-r["cpu"], -r["mem"]))[:n]
        picked = {r["pid"] for r in by_cpu}
        by_mem = [r for r in sorted(rows, key=lambda r: -r["mem"])[:n] if r["pid"] not in picked]
        picked |= {r["pid"] for r in by_mem}
        mine = [r for r in rows if r["own"] and r["pid"] not in picked]  # Kurooto's own are always listed
        return by_cpu + by_mem + mine


def own_pids(root: int | None) -> dict[int, str]:
    """Kurooto's processes: the assistant (`root`) and everything it started, pid -> name."""
    if not root:
        return {}
    try:
        p = psutil.Process(root)
        out = {root: "kurooto"}
        for c in p.children(recursive=True):
            try:
                out[c.pid] = c.name()
            except psutil.Error:
                out[c.pid] = "?"
        return out
    except psutil.Error:
        return {}
