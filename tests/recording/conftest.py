"""Fixtures for recording E2E: BlackHole audio injection.

The recording scenario needs real audio on the system mic for Heidi to produce
a transcript. `audio_injection` routes I/O to BlackHole and loops a fixed clip
for the duration of the recording, then restores the original devices.

If BlackHole isn't installed (e.g. CI, or before `scripts/setup_audio.sh` +
reboot), the fixture yields a no-op player and the test can still exercise the
UI flow — it just won't get spoken content. Tests that REQUIRE audio should
call `require_blackhole`.
"""
import os
from pathlib import Path

import pytest

from lib import audio

CLIP = Path(__file__).resolve().parent.parent.parent / "assets" / "consult_30s.wav"
RECORD_SECONDS = float(os.environ.get("RECORD_SECONDS", "30"))


@pytest.fixture()
def require_blackhole():
    if not audio.blackhole_available():
        pytest.skip(
            "BlackHole not available — run scripts/setup_audio.sh and reboot. "
            "See docs for macOS audio setup."
        )


@pytest.fixture()
def audio_injection():
    """Yield a callable start(seconds) that loops the clip via BlackHole.

    Routing is only switched if BlackHole is present; otherwise start() is a
    no-op so the UI flow still runs.
    """
    router = None
    procs = []

    def start(seconds: float = RECORD_SECONDS):
        nonlocal router
        if not CLIP.exists():
            pytest.skip(f"Fixed clip missing: {CLIP} (run scripts/setup_audio.sh)")
        if audio.blackhole_available():
            router = audio.AudioRouter()
            router.__enter__()
            procs.append(audio.play_clip(CLIP, seconds))
        # else: no audio device — caller still drives the UI

    yield start

    for p in procs:
        audio.stop_clip(p)
    if router is not None:
        router.__exit__(None, None, None)
