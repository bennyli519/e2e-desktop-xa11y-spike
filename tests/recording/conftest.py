"""recording domain: shared config + demo-friendly reporting.

This domain covers the Scribe session recording -> transcription -> note
generation flow at several durations, one file per flow:

    test_30s.py    30-second session      (fast e2e check)
    test_1min.py   1-minute session
    test_5min.py   5-minute session       (long-session stress)
    test_10min.py  10-minute session      (long-session stress)

Each file runs the flow ONCE (module-scoped `result` fixture) and then exposes
one visible test per assertion (recording starts / timer advances / transcript
generated / note generated / transcript accuracy). That gives a natural
checklist in the pytest output and the HTML report.

Audio is injected via BlackHole (see lib/audio.py + scripts/setup_audio.sh).
Without BlackHole the structural checks (start/timer/note-started) still run and
the content checks skip cleanly.

Run from Ghostty (needs Accessibility + Screen Recording), logged in, Heidi
foreground:

    .venv/bin/python3.14 -m pytest tests/recording/ -v          # all durations
    .venv/bin/python3.14 -m pytest tests/recording/ -m "not longsession"  # 30s only
    .venv/bin/python3.14 -m pytest tests/recording/test_5min.py -v

An HTML report is written to reports/report.html by default (see pyproject).
"""
from __future__ import annotations

import pytest

from _flow import FLOW_RESULTS, RecordingResult

# Fixed order for the summary table regardless of collection order.
_FLOW_ORDER = ["30s", "1min", "5min", "10min"]

_CHECK = "\u2713"   # ✓
_CROSS = "\u2717"   # ✗
_DASH = "\u2014"    # —

# ANSI colours for the terminal table (pytest already emits colour by default).
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _flow_lines(res: RecordingResult) -> list[tuple[str, bool | None, str]]:
    """(label, ok, detail) rows for one flow. ok=None => not applicable/skip."""
    if res.error:
        return [("flow crashed", False, res.error[:60])]

    acc = res.transcript_accuracy
    audio = res.audio_injected
    return [
        ("recording started", res.recording_started, ""),
        ("timer advanced",
         res.timer_advanced,
         f"reached {res.timer_last_s}s" if res.timer_last_s is not None else "no timer"),
        ("transcription generated",
         bool(res.transcript.strip()) if audio else None,
         "" if audio else "no audio"),
        ("note generated",
         (res.note_started and bool(res.note.strip())) if audio else res.note_started,
         "" if audio else "started only (no audio)"),
        ("duration display correct",
         (res.duration_display_s is not None and res.timer_last_s is not None
          and abs(res.duration_display_s - res.timer_last_s)
          <= max(3, int(res.timer_last_s * 0.05))),
         f"shows {res.duration_display}" if res.duration_display
         else "no duration shown"),
        ("transcript accuracy",
         (acc >= res.transcript_threshold) if audio else None,
         f"{acc:.1%} ({len(res.hits)}/{len(res.keywords)}), "
         f"thr {res.transcript_threshold:.0%}" if audio else "no audio"),
    ]


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print a demo-friendly per-flow checklist after the run."""
    if not FLOW_RESULTS:
        return

    tr = terminalreporter
    tr.write_line("")
    tr.write_line(f"{_BOLD}{'=' * 66}{_RESET}")
    tr.write_line(f"{_BOLD}  RECORDING E2E — FLOW RESULTS{_RESET}")
    tr.write_line(f"{_BOLD}{'=' * 66}{_RESET}")

    for flow in _FLOW_ORDER:
        res = FLOW_RESULTS.get(flow)
        if res is None:
            continue
        rows = _flow_lines(res)
        flow_ok = all(ok for _, ok, _ in rows if ok is not None)
        head_colour = _GREEN if flow_ok else _RED
        head_mark = _CHECK if flow_ok else _CROSS
        secs = f"{res.seconds:g}s"
        tr.write_line("")
        tr.write_line(
            f"{head_colour}{_BOLD}{head_mark} {flow} session{_RESET}"
            f"{_DIM}  (recorded {secs}){_RESET}"
        )
        for label, ok, detail in rows:
            if ok is None:
                mark, colour = _DASH, _YELLOW
            elif ok:
                mark, colour = _CHECK, _GREEN
            else:
                mark, colour = _CROSS, _RED
            line = f"    {colour}{mark}{_RESET} {label:<26}"
            if detail:
                line += f" {_DIM}{detail}{_RESET}"
            tr.write_line(line)

    tr.write_line("")
    tr.write_line(f"{_BOLD}{'=' * 66}{_RESET}")
    tr.write_line(
        f"  {_DIM}legend:{_RESET} {_GREEN}{_CHECK} pass{_RESET}  "
        f"{_RED}{_CROSS} fail{_RESET}  "
        f"{_YELLOW}{_DASH} skipped (no audio / n/a){_RESET}"
    )
    tr.write_line(f"{_BOLD}{'=' * 66}{_RESET}")
    tr.write_line("")


def pytest_html_report_title(report):
    report.title = "Heidi Recording E2E Report"
