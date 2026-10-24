#!/usr/bin/env bash
# Brain's optional hardened mode (Kurooto 0.8.0, Linux with systemd, macOS with launchd).
#
# Runs Brain's scorekeeper as a system user of its own (kurooto-mind), so that not even a program running as you can
# change Brain's log or scores. Without it Brain works the same; the scorekeeper just runs as you.
#
#   sudo tools/mind_harden.sh                 print what it would do (nothing is changed)
#   sudo tools/mind_harden.sh --apply         do it
#   sudo tools/mind_harden.sh --undo          put everything back as it was (Brain's data stays)
#
# Options: --owner NAME (default: the user who ran sudo), --state DIR (Kurooto's state folder; default: what
# `kurooto paths` says for the owner).
#
# What --apply does, in order:
#   1. creates the system user and group kurooto-mind (no home, no login), and adds kurooto-mind to nothing;
#   2. stops Kurooto's own scorekeeper by turning on hardened mode first (the marker file below), and waits for it;
#   3. moves <state>/mind to /var/lib/kurooto-mind/<owner> (owner kurooto-mind, group the owner's group, 0750; files
#      0640) and leaves a symlink at <state>/mind, so Kurooto reads it where it was;
#   4. installs a private copy of the scorekeeper (kurooto/mind and its two libraries, filelock and psutil) in
#      /opt/kurooto-mind with its own Python environment, so the scorekeeper never runs code from your home folder;
#   5. a systemd unit (kurooto-mind@<owner>.service) or a launchd daemon (io.github.avtarfr.kurooto-mind.<owner>)
#      that runs it as kurooto-mind, restarting it if it stops;
#   6. writes the marker <dir>/hardened, which tells Kurooto not to start a scorekeeper of its own.
#
# After a Kurooto update that changes the scorekeeper (the changelog says so), run --apply again; it's safe to run
# twice. While the scorekeeper is down in this mode, facts aren't kept aside for it (its folder isn't yours to write).
set -euo pipefail
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

MODE=plan
OWNER="${SUDO_USER:-}"
STATE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) MODE=apply ;;
    --undo) MODE=undo ;;
    --owner) OWNER="$2"; shift ;;
    --state) STATE="$2"; shift ;;
    -h|--help) sed -n '2,28p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

OS="$(uname -s)"
case "$OS" in Linux|Darwin) ;; *) echo "Hardened mode is for Linux and macOS." >&2; exit 2 ;; esac
[ -n "$OWNER" ] || { echo "Run it with sudo (or pass --owner NAME)." >&2; exit 2; }
id "$OWNER" >/dev/null 2>&1 || { echo "No user called $OWNER." >&2; exit 2; }
if [ "$MODE" != plan ] && [ "$(id -u)" != 0 ]; then echo "--apply and --undo need sudo." >&2; exit 2; fi

HOME_DIR="$(eval echo "~$OWNER")"
GROUP="$(id -gn "$OWNER")"
if [ -z "$STATE" ]; then
  STATE="$(sudo -u "$OWNER" -H env -i HOME="$HOME_DIR" PATH="$HOME_DIR/.local/bin:/usr/local/bin:/usr/bin:/bin" \
    kurooto paths 2>/dev/null | awk '$1 == "state" { $1 = ""; sub(/^ /, ""); print; exit }')" || true
fi
[ -n "$STATE" ] && [ -d "$STATE" ] || { echo "Couldn't find Kurooto's state folder; pass --state DIR." >&2; exit 2; }

LINK="$STATE/mind"
DEST="/var/lib/kurooto-mind/$OWNER"
OPT="/opt/kurooto-mind"
SRC="$(cd "$(dirname "$0")/.." && pwd)/src/kurooto"
UNIT="kurooto-mind@$OWNER.service"
DSUSER="/""Users/kurooto-mind"  # (macOS) the user's record in the directory service, not a home folder
PLIST="/Library/LaunchDaemons/io.github.avtarfr.kurooto-mind.$OWNER.plist"

say() { echo "$*"; }
run() { if [ "$MODE" = plan ]; then say "  would: $*"; else "$@"; fi; }

wait_for_own_keeper_to_stop() {
  local i=0
  while [ -f "$1/endpoint.json" ] && [ $i -lt 30 ]; do sleep 1; i=$((i + 1)); done
}

if [ "$MODE" = undo ]; then
  say "Undoing Brain's hardened mode for $OWNER."
  if [ "$OS" = Linux ]; then
    systemctl disable --now "$UNIT" 2>/dev/null || true
    rm -f "/etc/systemd/system/kurooto-mind@.service"
    systemctl daemon-reload
  else
    launchctl bootout system "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
  fi
  if [ -L "$LINK" ] && [ -d "$DEST" ]; then
    rm -f "$LINK"
    rm -f "$DEST/hardened" "$DEST/endpoint.json" "$DEST/key" "$DEST/alive"
    mv "$DEST" "$LINK"
    chown -R "$OWNER:$GROUP" "$LINK"
    chmod 0700 "$LINK"
    find "$LINK" -type f -exec chmod 0600 {} +
  fi
  say "Done: Kurooto starts its own scorekeeper again (within a minute). /opt/kurooto-mind and the user kurooto-mind"
  say "stay; remove them with: sudo rm -rf $OPT; sudo userdel kurooto-mind (Linux) or dscl . -delete \"$DSUSER\" (macOS)."
  exit 0
fi

say "Brain's hardened mode for $OWNER (${MODE}):"
say "  state folder: $STATE"
say "  Brain's folder moves to $DEST (a symlink stays at $LINK)"
say "  the scorekeeper's own copy goes to $OPT"

# 1. the user
if ! id kurooto-mind >/dev/null 2>&1; then
  if [ "$OS" = Linux ]; then
    run useradd --system --no-create-home --shell /usr/sbin/nologin --user-group kurooto-mind
  else
    say "  (macOS) creating the hidden system user kurooto-mind"
    if [ "$MODE" = apply ]; then
      uid=400; while dscl . -list /Users UniqueID | awk '{print $2}' | grep -qx "$uid"; do uid=$((uid + 1)); done
      dscl . -create /Groups/kurooto-mind PrimaryGroupID "$uid"
      dscl . -create "$DSUSER" UniqueID "$uid"
      dscl . -create "$DSUSER" PrimaryGroupID "$uid"
      dscl . -create "$DSUSER" UserShell /usr/bin/false
      dscl . -create "$DSUSER" NFSHomeDirectory /var/empty
      dscl . -create "$DSUSER" IsHidden 1
    fi
  fi
fi

# 2. Kurooto stops its own scorekeeper (the marker), then 3. the folder moves
if [ -d "$LINK" ] && [ ! -L "$LINK" ]; then
  run touch "$LINK/hardened"
  [ "$MODE" = apply ] && wait_for_own_keeper_to_stop "$LINK"
  run mkdir -p "$(dirname "$DEST")"
  run mv "$LINK" "$DEST"
  run ln -s "$DEST" "$LINK"
  run chown -h "$OWNER:$GROUP" "$LINK"
elif [ ! -e "$LINK" ]; then
  run mkdir -p "$DEST"
  run ln -s "$DEST" "$LINK"
  run chown -h "$OWNER:$GROUP" "$LINK"
fi
run chown -R "kurooto-mind:$GROUP" "$DEST"
run chmod 0750 "$DEST"
[ "$MODE" = apply ] && find "$DEST" -type f -exec chmod 0640 {} +
run touch "$DEST/hardened"
run chown "kurooto-mind:$GROUP" "$DEST/hardened"
run chmod 0640 "$DEST/hardened"
# Kurooto's own logs folder isn't writable by kurooto-mind: the scorekeeper's errors go to the system log instead

# 4. the scorekeeper's own copy, with its own Python
PY="$(command -v python3)"
run mkdir -p "$OPT/lib/kurooto/mind"
if [ "$MODE" = apply ]; then
  "$PY" -m venv "$OPT/venv"
  "$OPT/venv/bin/pip" install --quiet --upgrade filelock psutil
  : > "$OPT/lib/kurooto/__init__.py"
  cp "$SRC"/mind/{__init__,log,score,scorekeeper,records,whitelist}.py "$OPT/lib/kurooto/mind/"
  chown -R root:root "$OPT"
  chmod -R go-w "$OPT"
else
  say "  would: $PY -m venv $OPT/venv; pip install filelock psutil; copy $SRC/mind/{__init__,log,score,scorekeeper,records,whitelist}.py"
fi

# 5. the service
CMD="$OPT/venv/bin/python -m kurooto.mind.scorekeeper --dir $DEST --hardened"
if [ "$OS" = Linux ]; then
  if [ "$MODE" = apply ]; then
    cat > /etc/systemd/system/kurooto-mind@.service <<EOF
[Unit]
Description=Kurooto Brain scorekeeper for %i
After=local-fs.target

[Service]
User=kurooto-mind
Group=kurooto-mind
Environment=PYTHONPATH=$OPT/lib
ExecStart=$OPT/venv/bin/python -m kurooto.mind.scorekeeper --dir /var/lib/kurooto-mind/%i --hardened
UMask=0027
Restart=always
RestartSec=2
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/kurooto-mind/%i
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable --now "$UNIT"
  else
    say "  would: write /etc/systemd/system/kurooto-mind@.service and systemctl enable --now $UNIT"
  fi
else
  if [ "$MODE" = apply ]; then
    cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>io.github.avtarfr.kurooto-mind.$OWNER</string>
  <key>UserName</key><string>kurooto-mind</string>
  <key>ProgramArguments</key><array>
    <string>$OPT/venv/bin/python</string><string>-m</string><string>kurooto.mind.scorekeeper</string>
    <string>--dir</string><string>$DEST</string><string>--hardened</string>
  </array>
  <key>EnvironmentVariables</key><dict><key>PYTHONPATH</key><string>$OPT/lib</string></dict>
  <key>Umask</key><integer>23</integer>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><true/>
</dict></plist>
EOF
    launchctl bootstrap system "$PLIST"
  else
    say "  would: write $PLIST and launchctl bootstrap system it"
  fi
fi
say "  the scorekeeper runs as: $CMD"

if [ "$MODE" = plan ]; then
  say "Nothing was changed. Run again with --apply to do it."
else
  say "Done. /mind on Telegram should say \"running as its own user (hardened mode)\" within a minute."
fi
