# Kurooto installer for Windows. Paste this in PowerShell:
#     irm https://avtarfr.github.io/kurooto/install.ps1 | iex
# It installs uv (a small Python manager), Python 3.12 and Kurooto for your user only (no admin rights),
# turns on start-at-sign-in, starts Kurooto, and opens the setup page in your browser.
# Run it again any time to repair or update. Uninstall: kurooto uninstall (or Settings > Apps).
# Testers: KUROOTO_CHANNEL=beta installs from the beta channel, and the install keeps following it:
#     $env:KUROOTO_CHANNEL = 'beta'; irm https://avtarfr.github.io/kurooto/install.ps1 | iex
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$UvVersion = '0.13.1'

function Say($text) { Write-Host "  $text" }
Write-Host ''
Write-Host '  KUROOTO' -ForegroundColor Magenta
Say 'Setting up your assistant. This takes a few minutes the first time.'
$Channel = if ($env:KUROOTO_CHANNEL) { $env:KUROOTO_CHANNEL } else { 'stable' }  # testers: beta
if ($Channel -cnotmatch '^[a-z0-9-]+$') { throw "KUROOTO_CHANNEL is stable or beta, not '$Channel'. Nothing was installed." }
if ($Channel -ne 'stable') { Say "From the $Channel channel (pre-releases, for testers)." }

# 1. room on the disk
$drive = (Get-Item $env:LOCALAPPDATA).PSDrive
$freeGB = [math]::Round($drive.Free / 1GB, 1)
if ($freeGB -lt 2) { throw "Only $freeGB GB free on $($drive.Name):. Kurooto needs at least 2 GB to install. Free some space and run this again." }
Say "Free space on $($drive.Name): $freeGB GB. Fine."

# 2. uv (installs Python for us), pinned version, for this user only
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Say "Installing uv $UvVersion..."
    Invoke-RestMethod "https://astral.sh/uv/$UvVersion/install.ps1" | Invoke-Expression
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}
uv --version | Out-Null

# 3. Python 3.12, then Kurooto: bootstrap.py checks the release signature and every file's checksum first
Say 'Installing Python 3.12...'
uv python install 3.12 | Out-Null
$tmp = Join-Path ([System.IO.Path]::GetTempPath()) "kurooto-bootstrap.py"
if ($env:KUROOTO_SOURCE) {
    Copy-Item (Join-Path $env:KUROOTO_SOURCE 'installer\bootstrap.py') $tmp -Force
    uv run --no-project --python 3.12 --with 'cryptography>=43' $tmp --source $env:KUROOTO_SOURCE --channel $Channel
} else {
    $base = if ($env:KUROOTO_UPDATE_BASE) { $env:KUROOTO_UPDATE_BASE } else { 'https://avtarfr.github.io/kurooto' }
    Invoke-WebRequest "$base/bootstrap.py" -OutFile $tmp -UseBasicParsing
    uv run --no-project --python 3.12 --with 'cryptography>=43' $tmp --channel $Channel
}
if ($LASTEXITCODE -ne 0) { throw 'Kurooto did not install. Nothing else was changed; you can run this again.' }
Remove-Item $tmp -ErrorAction SilentlyContinue
Write-Host ''
# the kurooto command works in this window too (Kurooto put its folder on your user PATH for new windows)
$bin = Join-Path $HOME '.local\bin'
if (($env:Path -split ';') -notcontains $bin) { $env:Path = "$bin;$env:Path" }
Say 'Done. If the setup page did not open, run:  kurooto open'
Say 'Kurooto keeps running in the background and starts when you sign in.'
