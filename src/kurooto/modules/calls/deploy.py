"""Make (or update) your call line: a Cloudflare Worker on your own free Cloudflare account.

What it does, in order (each step is safe to repeat):
  1. Node.js into Kurooto's folder if it isn't there; the line's code (shipped with Kurooto) into app/call-line,
     its pinned packages (npm ci), and the call page bundled.
  2. Cloudflare sign-in. wrangler runs with its own home folder inside Kurooto's config, so it never sees or
     changes any other Cloudflare login on this computer. The sign-in link opens in your browser.
  3. Your account's workers.dev subdomain (made for you if you don't have one: k-<random>; it is public).
  4. Secrets made here (call secret, connector secret, ntfy topic and key, Web Push keys), the deploy, then the
     secrets (with your Gemini key) sent to Cloudflare in one go.
  5. A health check, then this computer connects to it.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import time
import tomllib
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable
from pathlib import Path

from kurooto import __version__
from kurooto.core import proc
from kurooto.core.prereqs import Prereqs
from kurooto.modules.calls import line

SOURCE = Path(__file__).resolve().parent.parent.parent / "data" / "worker"
FILES = ("src", "web", "public", "package.json", "package-lock.json", "wrangler.template.toml")
API = "https://api.cloudflare.com/client/v4"
Progress = Callable[[str], None]


def source_hash(src: Path = SOURCE) -> str:
    """Changes whenever the line's code does (so an update knows to redeploy it)."""
    h = hashlib.sha256()
    for name in FILES:
        p = src / name
        for f in sorted(p.rglob("*") if p.is_dir() else [p]):
            built = f.name == "app.js" and f.parent.name == "public"  # made from web/app.js at deploy time
            if f.is_file() and "node_modules" not in f.parts and not built:
                h.update(f.relative_to(src).as_posix().encode())
                h.update(f.read_bytes())
    return h.hexdigest()[:16]


def wrangler_env(config_dir: Path, cache_dir: Path, account: str = "") -> dict:
    """wrangler's own home: its login lives here and nowhere else (it also checks ~/.wrangler, so HOME moves too)."""
    home = config_dir / "cloudflare"
    home.mkdir(parents=True, exist_ok=True)
    try:
        home.chmod(0o700)
    except OSError:
        pass
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLOUDFLARE_", "CF_", "WRANGLER_"))}
    env.update(
        HOME=str(home),
        USERPROFILE=str(home),
        XDG_CONFIG_HOME=str(home),
        WRANGLER_SEND_METRICS="false",
        npm_config_cache=str(cache_dir / "npm"),
        npm_config_update_notifier="false",
        NO_COLOR="1",
    )
    if account:
        env["CLOUDFLARE_ACCOUNT_ID"] = account
    return env


def oauth_token(config_dir: Path) -> str | None:
    f = config_dir / "cloudflare" / ".wrangler" / "config" / "default.toml"
    try:
        return tomllib.loads(f.read_text(encoding="utf-8")).get("oauth_token")
    except (OSError, tomllib.TOMLDecodeError):
        return None


def accounts_from_whoami(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"\b[0-9a-f]{32}\b", text)))


def skip_built(folder: str, names: list[str]) -> set[str]:
    """What not to copy into the call line's folder: installed packages, and the BUILT page (public/app.js), which is
    made fresh. Never the source web/app.js: skipping every "app.js" once left nothing to build, so no call line could
    be set up."""
    skip = {"node_modules"} & set(names)
    if Path(folder).name == "public" and "app.js" in names:
        skip.add("app.js")
    return skip


def toml_str(v: str) -> str:
    return json.dumps(str(v))[1:-1]  # a TOML basic string accepts JSON's escapes


def render_toml(template: str, values: dict) -> str:
    out = template
    for k, v in values.items():
        out = out.replace("{" + k + "}", toml_str(v))
    left = re.findall(r'"\{([a-z_]+)\}"', out)
    if left:
        raise ValueError(f"no value for {left}")
    return out


def new_name() -> str:
    return "kurooto-" + "".join(secrets.choice("abcdefghijkmnpqrstuvwxyz23456789") for _ in range(6))


def ensure_secrets(app) -> dict:
    """The line's secrets: made once, kept in your keychain, reused on every redeploy."""
    sec = app.secrets
    made = {
        "calls.call_secret": lambda: secrets.token_hex(32),
        "calls.connector_secret": lambda: secrets.token_hex(32),
        "calls.ntfy_topic": lambda: "kurooto-" + secrets.token_hex(12),
        "calls.ntfy_key": line.new_key,
    }
    for k, fn in made.items():
        if not sec.get(k):
            sec.set(k, fn())
    if not sec.get("calls.vapid_jwk") or not sec.get("calls.vapid_public"):
        jwk, pub = line.vapid_keys()
        sec.set("calls.vapid_jwk", jwk)
        sec.set("calls.vapid_public", pub)
    return {
        "CALL_SECRET": sec.get("calls.call_secret"),
        "CONNECTOR_SECRET": sec.get("calls.connector_secret"),
        "GEMINI_API_KEY": sec.get("gemini.api_key"),
        "NTFY_TOPIC": sec.get("calls.ntfy_topic"),
        "NTFY_KEY": sec.get("calls.ntfy_key"),
        "VAPID_JWK": sec.get("calls.vapid_jwk"),
        "VAPID_PUBLIC": sec.get("calls.vapid_public"),
        **({"GITHUB_TOKEN": sec.get("calls.github_token")} if sec.get("calls.github_token") else {}),
    }


def cf_api(token: str, method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(  # noqa: S310 (Cloudflare's API, https)
        API + path,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except ValueError:
            return {"success": False, "errors": [{"message": f"HTTP {e.code}"}]}


def health(url: str, timeout: float = 10) -> dict | None:
    """Your call line's /health answer, or None. It says who's asking: Cloudflare turns Python's default user agent
    away (403, "error code: 1010"), which made a working line look dead to `kurooto doctor` and the health checks."""
    from kurooto import __version__

    req = urllib.request.Request(  # noqa: S310 (your call line, https)
        url.rstrip("/") + "/health", headers={"User-Agent": f"Kurooto/{__version__}", "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
            return json.loads(r.read())
    except (OSError, ValueError):
        return None


class Deployer:
    def __init__(self, app, progress: Progress = print, unattended: bool = False):
        self.app = app
        self.say = progress
        self.unattended = unattended  # nobody is watching (the redeploy after an update): never open a sign-in page
        self.dir = app.paths.app / "call-line"
        self.prereqs = Prereqs(app.paths.app, app.paths.cache)
        self.node: str | None = None
        self.account = ""

    # --------------------------------------------------------------------------------------- tools
    def _node(self) -> str:
        node = self.prereqs.items["node"].find()
        if not node:
            self.say("Installing Node.js (about 120 MB)…")
            ok, msg = self.prereqs.install("node", self.say)
            if not ok:
                raise RuntimeError(msg)
            node = self.prereqs.items["node"].find()
        if not node:
            raise RuntimeError("Node.js didn't install")
        return node

    def _npm_cli(self) -> list[str]:
        node = Path(self.node)
        for cand in (
            node.parent / "node_modules" / "npm" / "bin" / "npm-cli.js",
            node.parent.parent / "lib" / "node_modules" / "npm" / "bin" / "npm-cli.js",
        ):
            if cand.is_file():
                return [str(node), str(cand)]
        npm = shutil.which("npm", path=str(node.parent)) or shutil.which("npm")
        if not npm:
            raise RuntimeError("npm wasn't found next to Node.js")
        return [npm]

    def _env(self) -> dict:
        env = wrangler_env(self.app.paths.config, self.app.paths.cache, self.account)
        env["PATH"] = str(Path(self.node).parent) + os.pathsep + os.environ.get("PATH", "")
        return env

    def _wrangler(self, *args: str, input: str | None = None, timeout: float = 300) -> proc.Result:
        return proc.run(
            [self.node, str(self.dir / "node_modules" / "wrangler" / "bin" / "wrangler.js"), *args],
            input=input,
            timeout=timeout,
            cwd=self.dir,
            env=self._env(),
        )

    # --------------------------------------------------------------------------------------- steps
    def prepare(self) -> None:
        self.node = self._node()
        self.dir.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            src, dst = SOURCE / name, self.dir / name
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True, ignore=skip_built)
            else:
                shutil.copy2(src, dst)
        apk = SOURCE.parent / "kurooto.apk"
        if apk.is_file():
            shutil.copy2(apk, self.dir / "public" / "kurooto.apk")
        lock = (self.dir / "package-lock.json").read_bytes()
        stamp = self.dir / "node_modules" / ".kurooto-lock"
        if not stamp.is_file() or stamp.read_bytes() != hashlib.sha256(lock).digest():
            self.say("Getting the call line's packages (about 230 MB, once)…")
            r = proc.run(
                [*self._npm_cli(), "ci", "--no-audit", "--no-fund", "--ignore-scripts"],
                timeout=900,
                cwd=self.dir,
                env=self._env(),
            )
            if r.code != 0:
                raise RuntimeError("npm ci failed: " + (r.err or r.out)[-400:])
            stamp.write_bytes(hashlib.sha256(lock).digest())
        r = proc.run(
            [
                self.node,
                str(self.dir / "node_modules" / "esbuild" / "bin" / "esbuild"),
                "web/app.js",
                "--bundle",
                "--minify",
                "--format=esm",
                "--target=es2019",
                "--outfile=public/app.js",
                "--log-level=warning",
            ],
            timeout=180,
            cwd=self.dir,
            env=self._env(),
        )
        if r.code != 0:
            raise RuntimeError("building the call page failed: " + (r.err or r.out)[-400:])

    def signed_in(self) -> bool:
        r = self._wrangler("whoami", timeout=90)
        accounts = accounts_from_whoami(r.out)
        if r.code == 0 and accounts and "not authenticated" not in r.out.lower():
            self.account = self.app.settings.get("calls.worker.account") or accounts[0]
            if self.account not in accounts:
                self.account = accounts[0]
            return True
        return False

    def sign_in(self, wait_s: float = 600) -> None:
        if self.signed_in():
            return
        self.say("Sign in to Cloudflare in your browser (free account; make one there if you don't have it)…")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        p = subprocess.Popen(
            [
                self.node,
                str(self.dir / "node_modules" / "wrangler" / "bin" / "wrangler.js"),
                "login",
                "--browser=false",
            ],
            cwd=self.dir,
            env=self._env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
        )
        opened = False
        deadline = time.monotonic() + wait_s
        for ln in p.stdout:  # wrangler prints the sign-in link, then waits for the browser to come back
            m = re.search(r"https://dash\.cloudflare\.com/oauth2/auth\S+", ln)
            if m and not opened:
                opened = True
                self.say(f"Sign-in page: {m.group(0)}")
                try:
                    webbrowser.open(m.group(0))
                except Exception:
                    pass
            if time.monotonic() > deadline:
                break
        try:
            p.wait(timeout=max(1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            proc.kill_tree(p.pid)
            raise RuntimeError("the Cloudflare sign-in wasn't finished in time; try again") from None
        if not self.signed_in():
            raise RuntimeError("the Cloudflare sign-in didn't complete")

    def subdomain(self) -> str:
        token = oauth_token(self.app.paths.config)
        if not token:
            raise RuntimeError("no Cloudflare sign-in found")
        r = cf_api(token, "GET", f"/accounts/{self.account}/workers/subdomain")
        sub = (r.get("result") or {}).get("subdomain") if r.get("success") else None
        if sub:
            return sub
        sub = "k-" + secrets.token_hex(4)
        self.say(f"Your Cloudflare account has no workers.dev address yet; making {sub}.workers.dev (it is public).")
        r = cf_api(token, "PUT", f"/accounts/{self.account}/workers/subdomain", {"subdomain": sub})
        if not r.get("success"):
            raise RuntimeError(
                "couldn't make a workers.dev address: " + str((r.get("errors") or [{}])[0].get("message"))
            )
        return sub

    def write_config(self, name: str, url: str) -> None:
        s = self.app.settings
        values = {
            "name": name,
            "owner_id": "owner",
            "tz": s.get("you.timezone") or "UTC",
            "public_url": url,
            "version": f"{__version__}+{source_hash()}",
            "live_model": s.get("calls.live_model") or "gemini-3.8-live",
            "ntfy_server": s.get("calls.ntfy_server") or "https://ntfy.sh",
            "notes_repo": s.get("calls.notes_repo") or "",
        }
        tpl = (self.dir / "wrangler.template.toml").read_text(encoding="utf-8")
        (self.dir / "wrangler.toml").write_text(render_toml(tpl, values), encoding="utf-8")

    def run(self) -> tuple[bool, str]:
        app = self.app
        if not app.secrets.get("gemini.api_key"):
            return False, "Add your free Gemini key first (AI brain → Gemini API key); calls use it for the voice."
        if not app.settings.get("you.timezone"):
            return False, "Set your timezone first (Settings → You)."
        self.say("Preparing your call line…")
        self.prepare()
        if self.unattended and not self.signed_in():
            return False, "Cloudflare wants you to sign in again"
        self.sign_in()
        sub = self.subdomain()
        w = dict(app.settings.get("calls.worker") or {})
        name = w.get("name") or new_name()
        url = f"https://{name}.{sub}.workers.dev"
        self.write_config(name, url)
        sec = ensure_secrets(app)
        self.say(f"Deploying {name} to your Cloudflare account…")
        r = self._wrangler("deploy", timeout=600)
        if r.code != 0:
            return False, "Deploy failed: " + (r.err or r.out).strip()[-600:]
        self.say("Sending its secrets (your Gemini key and the line's own keys) to Cloudflare…")
        r = self._wrangler("secret", "bulk", input=json.dumps(sec), timeout=300)
        if r.code != 0:
            return False, "Setting the secrets failed: " + (r.err or r.out).strip()[-600:]
        app.settings.set(
            "calls.worker",
            {**w, "name": name, "url": url, "account": self.account, "hash": fingerprint(app), "deployed": time.time()},
        )
        self.say("Checking it answers (a new address can take a minute or two to appear)…")
        for _ in range(24):
            h = health(url)
            if h and h.get("ok"):
                app.events.emit("calls_deployed", version=h.get("version", ""))
                return True, f"Your call line is live at {url}. Pair your phone next (Phone → Pair a phone)."
            time.sleep(5)
        return (
            True,
            f"Deployed to {url}; it isn't answering yet (new addresses can take a few minutes). "
            "It'll connect by itself.",
        )


def deploy(app, progress: Progress = print, unattended: bool = False) -> tuple[bool, str]:
    try:
        return Deployer(app, progress, unattended).run()
    except Exception as e:
        return False, f"{e}"[:600]


def fingerprint(app) -> str:
    """The line's code plus the settings baked into it: when this changes, it's redeployed."""
    s = app.settings
    parts = [
        source_hash(),
        s.get("you.timezone") or "",
        s.get("calls.live_model") or "",
        s.get("calls.ntfy_server") or "",
        s.get("calls.notes_repo") or "",
        "gh" if app.secrets.get("calls.github_token") else "",
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def needs_redeploy(app) -> bool:
    w = app.settings.get("calls.worker") or {}
    return bool(w.get("url")) and w.get("hash") != fingerprint(app)
