#!/bin/bash
# One-shot bootstrap for the recording E2E on a fresh macOS machine.
#
# Automates everything that CAN be scripted:
#   - Homebrew deps (BlackHole, SwitchAudioSource)
#   - Python venv + package install
#   - Fixed consult audio generation
#   - CoreAudio reload so BlackHole appears
#   - Opens the two System Settings panes you must click by hand
#
# The two TCC permissions (Accessibility, Screen Recording) CANNOT be granted
# from the command line — Apple requires a manual toggle (or an MDM profile).
# This script opens the right panes and tells you exactly what to enable.
#
# Usage (from the terminal you'll run tests in, e.g. Ghostty):
#   bash scripts/bootstrap.sh
set -e

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

echo "════════════════════════════════════════════════"
echo " Recording E2E — one-shot bootstrap"
echo "════════════════════════════════════════════════"

# 1. Homebrew ------------------------------------------------------------------
if ! command -v brew >/dev/null 2>&1; then
  echo "!! Homebrew not found. Install it first: https://brew.sh"
  exit 1
fi

echo "==> [1/6] Installing audio tooling (SwitchAudioSource, BlackHole 2ch)"
brew install switchaudio-osx || true
# BlackHole needs sudo + reboot; brew will prompt for your password.
brew install blackhole-2ch || true

# 2. Python venv ---------------------------------------------------------------
echo "==> [2/6] Python venv + deps"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
./.venv/bin/pip install -q -e .

# 3. Audio clips ---------------------------------------------------------------
echo "==> [3/6] Generating fixed consult audio"
say -v Samantha -o assets/consult_30s.aiff \
"Doctor: Good morning, what brings you in today? \
Patient: I've had a persistent headache for about two weeks now, mostly in the afternoons. \
Doctor: Any nausea or sensitivity to light? \
Patient: Some light sensitivity, but no nausea. I've also been feeling more tired than usual. \
Doctor: Are you sleeping well? \
Patient: Not really, I've been waking up around three in the morning and struggle to fall back asleep. \
Doctor: Any recent changes in stress, diet, or caffeine intake? \
Patient: Work has been stressful, and I've probably been drinking more coffee than normal, maybe four cups a day. \
Doctor: Okay. Let's check your blood pressure and discuss some options."
afconvert assets/consult_30s.aiff assets/consult_30s.wav -d LEI16 -f WAVE
[ -f assets/consult_1min.txt ] && say -v Samantha -r 150 -f assets/consult_1min.txt -o assets/consult_1min.aiff && afconvert assets/consult_1min.aiff assets/consult_1min.wav -d LEI16 -f WAVE
[ -f assets/consult_5min.txt ] && say -v Samantha -r 150 -f assets/consult_5min.txt -o assets/consult_5min.aiff && afconvert assets/consult_5min.aiff assets/consult_5min.wav -d LEI16 -f WAVE
[ -f assets/consult_10min.txt ] && say -v Samantha -r 108 -f assets/consult_10min.txt -o assets/consult_10min.aiff && afconvert assets/consult_10min.aiff assets/consult_10min.wav -d LEI16 -f WAVE

# 4. Reload CoreAudio so BlackHole shows up ------------------------------------
echo "==> [4/6] Reloading CoreAudio (needs sudo) so BlackHole registers"
sudo killall coreaudiod 2>/dev/null || true
sleep 4

# 5. Open the permission panes -------------------------------------------------
echo "==> [5/6] Opening System Settings — grant these to THIS terminal:"
echo "      • Accessibility"
echo "      • Screen & System Audio Recording"
echo "    (then FULLY QUIT and reopen this terminal so the grant takes effect)"
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" || true
sleep 1
open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture" || true

# 6. Verify what we can --------------------------------------------------------
echo "==> [6/6] Verification"
printf "    BlackHole present:   "
if system_profiler SPAudioDataType 2>/dev/null | grep -qi BlackHole; then echo "YES"; else echo "NO (reboot may be required)"; fi
printf "    SwitchAudioSource:   "
if command -v SwitchAudioSource >/dev/null; then echo "YES"; else echo "NO"; fi
printf "    Audio clips:         "
if [ -f assets/consult_5min.wav ] && [ -f assets/consult_10min.wav ]; then echo "YES"; else echo "PARTIAL"; fi
printf "    Python/xa11y:        "
if ./.venv/bin/python -c "import xa11y" 2>/dev/null; then echo "YES"; else echo "NO"; fi

echo ""
echo "════════════════════════════════════════════════"
echo " Remaining MANUAL steps (cannot be scripted):"
echo "   1. In the two Settings panes just opened, enable this terminal."
echo "   2. Quit & reopen this terminal."
echo "   3. If BlackHole shows NO above: reboot, then re-run this script."
echo "   4. Open Heidi and log in once (Auth0 token then persists)."
echo ""
echo " Then run:"
echo "   source .venv/bin/activate"
echo "   pytest tests/recording/ -v -s -m 'not longsession'"
echo "════════════════════════════════════════════════"
