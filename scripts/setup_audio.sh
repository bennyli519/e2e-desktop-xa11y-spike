#!/bin/sh
# One-time audio setup for the recording E2E POC.
#
# Installs the BlackHole virtual audio device + SwitchAudioSource, and
# regenerates the fixed consult clip. BlackHole needs sudo (kernel audio
# driver) and a REBOOT to take effect — run this from a real terminal
# (Ghostty), not from an agent, so it can prompt for your password.
#
# Usage:  sh scripts/setup_audio.sh
set -e

echo "==> Installing SwitchAudioSource (CLI audio switcher)"
brew install switchaudio-osx || true

echo "==> Installing BlackHole 2ch (virtual loopback device — needs sudo + reboot)"
brew install blackhole-2ch || true

echo "==> Regenerating fixed consult clip (assets/consult_30s.wav)"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$REPO/assets"
say -v Samantha -o "$REPO/assets/consult_30s.aiff" \
"Doctor: Good morning, what brings you in today? \
Patient: I've had a persistent headache for about two weeks now, mostly in the afternoons. \
Doctor: Any nausea or sensitivity to light? \
Patient: Some light sensitivity, but no nausea. I've also been feeling more tired than usual. \
Doctor: Are you sleeping well? \
Patient: Not really, I've been waking up around three in the morning and struggle to fall back asleep. \
Doctor: Any recent changes in stress, diet, or caffeine intake? \
Patient: Work has been stressful, and I've probably been drinking more coffee than normal, maybe four cups a day. \
Doctor: Okay. Let's check your blood pressure and discuss some options to manage the headaches and improve your sleep."
afconvert "$REPO/assets/consult_30s.aiff" "$REPO/assets/consult_30s.wav" -d LEI16 -f WAVE

echo ""
echo "==> Done. IMPORTANT: reboot for BlackHole to appear as an audio device."
echo "    Verify after reboot:  SwitchAudioSource -a | grep BlackHole"
