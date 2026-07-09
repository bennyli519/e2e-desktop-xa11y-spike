"""One-shot: record with real audio injected via BlackHole, dump transcript.

Feeds assets/consult_30s.wav into Heidi's mic through the configured virtual
audio device, records ~30s, stops, waits for note generation, then dumps the
tree so we can see where the transcript text actually lives in the AX tree.

Run from Ghostty, Heidi logged in + foreground:
    PYTHONPATH=. .venv/bin/python3.14 scripts/probe_transcript.py
"""
import time
from pathlib import Path

import xa11y

from lib import audio
from pages import ScribePage
from pages.sidebar import Sidebar

REPORTS = Path(__file__).resolve().parent.parent / "reports"
CLIP = Path(__file__).resolve().parent.parent / "assets" / "consult_30s.wav"
SECONDS = 30


def main() -> int:
    app = xa11y.App.by_name("Heidi", timeout=10)
    print(
        f"connected pid={app.pid}, "
        f"virtual_audio={audio.virtual_audio_available()}, "
        f"input={audio.input_device_name()}"
    )

    sb = Sidebar(app)
    sb.reset_to_scribe()
    assert sb.new_session(), "could not start new session"
    rec = ScribePage(app)

    rec.start_recording()
    print("recording started:", rec.is_recording())

    injector = audio.AudioInjector(app)
    injected = injector.prepare()
    if injected:
        injector.play(CLIP, SECONDS)
        print(f"playing {CLIP.name} for {SECONDS}s...")
    else:
        print("virtual audio unavailable; recording without fixture injection")

    t0 = rec.recording_timer()
    time.sleep(SECONDS)
    t1 = rec.recording_timer()
    print(f"timer {t0} -> {t1}")

    injector.cleanup()
    print("audio stopped, devices restored")

    rec.stop_recording()
    print("recording stopped; waiting for note generation...")
    started = rec.wait_note_generation(timeout=60)
    print("note generation started:", started)

    # Give it time to actually produce transcript/note text.
    for i in range(24):  # up to 2 min
        time.sleep(5)
        tree = app.dump(max_depth=22)
        (REPORTS / "transcript_state.txt").write_text(tree)
        # look for the consult keywords appearing anywhere
        low = tree.lower()
        hits = [w for w in ["headache", "sleep", "coffee", "nausea", "stress",
                            "morning", "patient", "doctor"] if w in low]
        print(f"  +{(i+1)*5}s  tree={len(tree)}  keyword_hits={hits}")
        if len(hits) >= 2:
            print("  transcript content detected!")
            break

    print("\nsaved reports/transcript_state.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
