"""Play an audio fixture to a named output device.

Windows desktop recording tests use this to route fixture audio into
VB-CABLE's playback side (for example, "CABLE Input"), while Heidi records
from the corresponding capture side ("CABLE Output").
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def _die(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def _windows_play(path: Path, device_hint: str) -> int:
    try:
        import miniaudio
    except ImportError:
        return _die(
            "miniaudio is required for Windows device-specific playback. "
            "Run: python -m pip install -e ."
        )

    devices = miniaudio.Devices()
    playbacks = devices.get_playbacks()
    playback = next(
        (device for device in playbacks if device_hint.lower() in device["name"].lower()),
        None,
    )
    if playback is None:
        names = "\n".join(f"  - {device['name']}" for device in playbacks)
        return _die(f"Playback device containing {device_hint!r} not found:\n{names}")

    info = miniaudio.get_file_info(str(path))
    sample_rate = info.sample_rate or 48000
    nchannels = max(info.nchannels or 1, 2)
    output_format = miniaudio.SampleFormat.SIGNED16
    duration = info.duration or 0

    print(
        f"Playing {path} ({duration:.1f}s) to {playback['name']}",
        flush=True,
    )
    stream = miniaudio.stream_file(
        str(path),
        output_format=output_format,
        nchannels=nchannels,
        sample_rate=sample_rate,
    )
    next(stream)

    with miniaudio.PlaybackDevice(
        device_id=playback["id"],
        output_format=output_format,
        nchannels=nchannels,
        sample_rate=sample_rate,
    ) as device:
        device.start(stream)
        # miniaudio streams until the generator is exhausted; sleeping for the
        # known duration keeps the helper process alive for the recording window.
        time.sleep(duration + 0.5)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument(
        "--device",
        default="CABLE Input",
        help="case-insensitive playback-device name fragment",
    )
    args = parser.parse_args()

    path = args.file.expanduser().resolve()
    if not path.exists():
        return _die(f"Audio fixture does not exist: {path}")

    if sys.platform == "win32":
        return _windows_play(path, args.device)

    return _die("Device-specific playback helper is currently implemented for Windows")


if __name__ == "__main__":
    raise SystemExit(main())
