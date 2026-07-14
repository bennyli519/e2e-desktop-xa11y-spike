"""Dump the Transcript tab tree so we can see WHERE the transcript body lives.

We suspect the read grabs the wrong nodes (sidebar noise / placeholder) instead
of the real transcript text. Run this while a session that ALREADY HAS a fully
generated transcript is open (e.g. right after a successful upload), on the
Scribe page.

RUN FROM GHOSTTY, Heidi frontmost:
    .venv/bin/python scripts/dump_transcript.py

Outputs:
  reports/transcript_tab.txt        full AX tree of the Transcript tab
  reports/transcript_bodytext.txt   what _body_text() currently returns
  reports/transcript_clinical.txt   what visible_clinical_text() returns
Paste all three back.
"""
import sys
import time
from pathlib import Path

import xa11y

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import activate_app  # noqa: E402
from pages import ScribePage  # noqa: E402

REPORTS = Path(__file__).resolve().parent.parent / "reports"


def main() -> None:
    app = xa11y.App.by_name("Heidi", timeout=10.0)
    activate_app("Heidi")
    time.sleep(2.0)

    rec = ScribePage(app)
    # Switch to the Transcript tab and give it a moment.
    opened = rec.open_tab("Transcript")
    print(f"open_tab('Transcript') -> {opened}")
    time.sleep(1.5)

    REPORTS.mkdir(exist_ok=True)

    tree = app.dump(max_depth=25)
    (REPORTS / "transcript_tab.txt").write_text(tree, encoding="utf-8")
    print(f"saved reports/transcript_tab.txt ({len(tree)} chars)")

    body = rec._body_text()
    (REPORTS / "transcript_bodytext.txt").write_text(body, encoding="utf-8")
    print(f"\n=== _body_text() [{len(body)} chars] ===")
    print(body[:1200])

    clinical = rec.visible_clinical_text()
    (REPORTS / "transcript_clinical.txt").write_text(clinical, encoding="utf-8")
    print(f"\n=== visible_clinical_text() [{len(clinical)} chars] ===")
    print(clinical[:1200])

    # Also enumerate text-bearing nodes by role so we can see if the transcript
    # is in a text_area / group value rather than static_text.
    print("\n=== node roles carrying long text (>40 chars) ===")
    lines = []
    for role in ["static_text", "text_area", "text_field", "group",
                 "paragraph", "document", "generic", "list", "cell"]:
        try:
            els = app.locator(role).elements()
        except Exception:
            continue
        for el in els:
            txt = (getattr(el, "value", "") or getattr(el, "name", "") or "")
            txt = txt.strip()
            if len(txt) > 40:
                lines.append(f"[{role}] ({len(txt)} chars) {txt[:100]!r}")
    out = "\n".join(lines)
    print(out)
    (REPORTS / "transcript_longnodes.txt").write_text(out, encoding="utf-8")
    print("\nsaved reports/transcript_longnodes.txt")
    print("\nDONE. Paste reports/transcript_longnodes.txt + transcript_clinical.txt back.")


if __name__ == "__main__":
    main()
