"""tests/scribe: shared config + demo-friendly reporting for Scribe TCD flows.

This feature folder groups the Scribe test cases from the 2.5.0 release plan,
sub-divided by flow:

    tests/scribe/recording/      TCD006 transcribe 5min, TCD007 dictate 5min
    tests/scribe/pause-resume/   TCD015 context, TCD016 transcript continuity
    tests/scribe/upload/         TCD004/005/008 audio (+context) upload
    tests/scribe/usb-headset/    TCD009-012 USB headset (+ mid-session disconnect)

Each TCD file runs its flow ONCE (module-scoped `result` fixture) and exposes
one visible test per acceptance criterion, so pytest output reads like the
Notion checklist.

Shared engine/asserts live at this level (_scribe_flow.py, _scribe_cases.py);
this conftest puts them on sys.path so the sub-folders can `from _scribe_flow
import ...` regardless of pytest's rootdir.

Run from Ghostty (needs Accessibility + Screen Recording), logged in, Heidi
foreground:

    .venv/bin/python -m pytest tests/scribe -v
    .venv/bin/python -m pytest tests/scribe/pause-resume -v
    .venv/bin/python -m pytest tests/scribe -m "not slow"   # skip 5-min flows
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make the shared engine/asserts importable from the sub-folders.
_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from _scribe_flow import (  # noqa: E402
    PAUSE_RESUME_RESULTS,
    SCRIBE_RESULTS,
    PauseResumeResult,
    ScribeResult,
)


# ---------------------------------------------------------------------------
# Guard fixtures
# ---------------------------------------------------------------------------
def _usb_headset_present() -> bool:
    """True if a USB/external audio input other than the built-in mic exists.

    macOS: query SwitchAudioSource for input devices; treat anything that
    isn't the built-in mic / virtual loopback as a candidate USB headset.
    Set HEIDI_E2E_USB_HEADSET to the exact device name to be explicit.
    """
    want = os.environ.get("HEIDI_E2E_USB_HEADSET")
    try:
        import subprocess
        out = subprocess.run(
            ["SwitchAudioSource", "-a", "-t", "input"],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except Exception:
        return False
    if want:
        return want.lower() in out.lower()
    ignore = ("macbook", "built-in", "blackhole", "aggregate", "virtual")
    for line in out.splitlines():
        name = line.strip().lower()
        if name and not any(tok in name for tok in ignore):
            return True
    return False


@pytest.fixture()
def require_usb_headset():
    """Skip unless a USB headset input is available.

    USB-headset cases (TCD009-012) need a real external audio device. Without
    one they skip cleanly. Set HEIDI_E2E_USB_HEADSET=<device name> to pin a
    specific device.
    """
    if not _usb_headset_present():
        pytest.skip(
            "No USB headset input detected — connect one (or set "
            "HEIDI_E2E_USB_HEADSET=<device name>) to run this flow"
        )


@pytest.fixture()
def require_manual():
    """Marker fixture: needs a human to physically (dis)connect the headset.

    Set RUN_MANUAL=1 to actually run; otherwise skip. Used by the mid-session
    disconnect cases (TCD011/012).
    """
    if os.environ.get("RUN_MANUAL") != "1":
        pytest.skip(
            "Needs manual physical-device interaction (headset disconnect) — "
            "set RUN_MANUAL=1 and follow the prompts to run"
        )


# ---------------------------------------------------------------------------
# Demo-friendly terminal summary
# ---------------------------------------------------------------------------
_CHECK = "\u2713"
_CROSS = "\u2717"
_DASH = "\u2014"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _rec_rows(res: ScribeResult):
    if res.error:
        return [("flow crashed", False, res.error[:60])]
    audio = res.audio_injected
    acc = res.transcript_accuracy
    if getattr(res, "is_upload", False):
        # Uploads have no live timer/duration; show the upload-relevant rows.
        rows = []
        if getattr(res, "context_uploaded", False) or getattr(res, "_has_context", False):
            rows.append(("context uploaded", res.context_uploaded, ""))
        rows += [
            ("upload accepted", res.recording_started, res.mode),
            ("transcription generated", bool(res.transcript.strip()), ""),
            ("note generated",
             (res.note_started and bool(res.note.strip())), ""),
            ("transcript accuracy (soft)",
             bool(res.hits),
             f"{acc:.1%} ({len(res.hits)}/{len(res.keywords)})"),
        ]
        return rows
    return [
        ("recording started", res.recording_started, res.mode),
        ("timer advanced",
         res.timer_advanced,
         f"reached {res.timer_last_s}s" if res.timer_last_s is not None else "no timer"),
        ("transcription generated",
         bool(res.transcript.strip()) if audio else None,
         "" if audio else "no audio"),
        ("note generated",
         (res.note_started and bool(res.note.strip())) if audio else res.note_started,
         "" if audio else "started only (no audio)"),
        ("transcript accuracy",
         (acc >= res.transcript_threshold) if audio else None,
         f"{acc:.1%} ({len(res.hits)}/{len(res.keywords)})" if audio else "no audio"),
    ]


def _pr_rows(res: PauseResumeResult):
    if res.error:
        return [("flow crashed", False, res.error[:60])]
    audio = res.audio_injected
    return [
        ("recording started", res.recording_started, res.mode),
        ("paused", res.paused, ""),
        ("resumed", res.resumed, ""),
        ("pre-pause content present",
         bool(res.seg_a_hits) if audio else None,
         f"{res.seg_a_hits}" if audio else "no audio"),
        ("post-resume content present",
         bool(res.seg_b_hits) if audio else None,
         f"{res.seg_b_hits}" if audio else "no audio"),
        ("no errors", (res.note_started and not res.has_error_banner), ""),
    ]


def _print_group(tr, title, results, row_fn):
    if not results:
        return
    tr.write_line("")
    tr.write_line(f"{_BOLD}{'=' * 66}{_RESET}")
    tr.write_line(f"{_BOLD}  {title}{_RESET}")
    tr.write_line(f"{_BOLD}{'=' * 66}{_RESET}")
    for flow, res in results.items():
        rows = row_fn(res)
        ok = all(o for _, o, _ in rows if o is not None)
        head_c = _GREEN if ok else _RED
        head_m = _CHECK if ok else _CROSS
        tr.write_line("")
        tr.write_line(f"{head_c}{_BOLD}{head_m} {flow}{_RESET}")
        for label, o, detail in rows:
            if o is None:
                mark, colour = _DASH, _YELLOW
            elif o:
                mark, colour = _CHECK, _GREEN
            else:
                mark, colour = _CROSS, _RED
            line = f"    {colour}{mark}{_RESET} {label:<28}"
            if detail:
                line += f" {_DIM}{detail}{_RESET}"
            tr.write_line(line)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not SCRIBE_RESULTS and not PAUSE_RESUME_RESULTS:
        return
    tr = terminalreporter
    _print_group(tr, "SCRIBE RECORDING E2E — FLOW RESULTS", SCRIBE_RESULTS, _rec_rows)
    _print_group(tr, "SCRIBE PAUSE/RESUME E2E — FLOW RESULTS",
                 PAUSE_RESUME_RESULTS, _pr_rows)
    tr.write_line("")
    tr.write_line(
        f"  {_DIM}legend:{_RESET} {_GREEN}{_CHECK} pass{_RESET}  "
        f"{_RED}{_CROSS} fail{_RESET}  "
        f"{_YELLOW}{_DASH} skipped (no audio / n/a){_RESET}"
    )
    tr.write_line("")
