#!/bin/sh
# Generate the two DISTINCT clips used by the pause/resume TCD flows
# (TCD015 context continuity, TCD016 transcript continuity).
#
# The pause/resume test records segment A, pauses, resumes, then records
# segment B. To prove nothing was dropped across the pause boundary the two
# clips must contain clearly DIFFERENT content:
#
#   pause_seg_a.wav  -> headache / migraine consult   (KEYWORDS_PAUSE_SEG_A)
#   pause_seg_b.wav  -> diabetes / insulin consult    (KEYWORDS_PAUSE_SEG_B)
#
# Keep the spoken keywords in sync with KEYWORDS_PAUSE_SEG_A / _SEG_B in
# tests/scribe/_scribe_flow.py.
#
# macOS only (uses `say` + `afconvert`). Run from a real terminal:
#   sh scripts/make_pause_resume_clips.sh
set -e

REPO="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$REPO/assets"

echo "==> Generating segment A (headache / migraine)"
say -v Samantha -r 150 -o "$REPO/assets/pause_seg_a.aiff" \
"Doctor: What brings you in today? \
Patient: I've had a bad headache for the past week, it feels like a migraine. \
Doctor: Where is the pain located? \
Patient: Mostly across my forehead, and it's worst in the morning. \
Doctor: Any nausea or sensitivity to light? \
Patient: Yes, some nausea and I'm quite sensitive to light when it flares up."
afconvert "$REPO/assets/pause_seg_a.aiff" "$REPO/assets/pause_seg_a.wav" -d LEI16 -f WAVE

echo "==> Generating segment B (diabetes / insulin)"
say -v Samantha -r 150 -o "$REPO/assets/pause_seg_b.aiff" \
"Doctor: Let's talk about your diabetes now. \
Patient: My blood sugars have been high and I'm still adjusting my insulin. \
Doctor: Any increased thirst or fatigue? \
Patient: Yes, a lot of thirst and I feel constant fatigue during the day. \
Doctor: Any changes to your eyesight? \
Patient: My vision has been blurred at times, especially in the evening."
afconvert "$REPO/assets/pause_seg_b.aiff" "$REPO/assets/pause_seg_b.wav" -d LEI16 -f WAVE

echo "==> Clip durations:"
for f in pause_seg_a pause_seg_b; do
  python3 -c "import wave; w=wave.open('$REPO/assets/$f.wav'); print('  $f.wav', round(w.getnframes()/w.getframerate(),1),'s')"
done

echo ""
echo "==> Done. Two distinct clips written to assets/pause_seg_a.wav and pause_seg_b.wav"
