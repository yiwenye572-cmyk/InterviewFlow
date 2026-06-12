"""Static UI checklist for audit (automated proxy for manual walkthrough)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

CHECKS = [
    ("index.html", ["app-nav", "screen-progress-modal", "home.js"]),
    ("screening.html", ["app-nav", "screening.js"]),
    ("interview.html", ["app-nav", "live-content", "agenda-content", "hold-talk-btn"]),
    ("report.html", ["pollReportStatus", "formatRecommendation", "report-progress"]),
    ("job.html", ["app-nav"]),
    ("history.html", ["app-nav"]),
]

JS_CHECKS = [
    ("js/home.js", ["pollScreenBatch", "async: true"]),
    ("js/interview.js", ["endInterviewAsync", "renderLiveAssessment", "renderAgendaPanel"]),
    ("js/nav.js", ["initAppNav", "screeningHref"]),
    ("js/api.js", ["formatTimelineDimension", "formatLiveAssessmentText"]),
]


def main() -> None:
    failed = False
    for html, needles in CHECKS:
        path = STATIC / html
        text = path.read_text(encoding="utf-8")
        for n in needles:
            if n not in text:
                # report-progress may be inline id
                if n == "report-progress" and "report-progress-bar" in text:
                    continue
                print(f"[FAIL] {html} missing {n!r}")
                failed = True
            else:
                print(f"[PASS] {html} has {n}")
    for rel, needles in JS_CHECKS:
        path = STATIC / rel
        text = path.read_text(encoding="utf-8")
        for n in needles:
            if n not in text:
                print(f"[FAIL] {rel} missing {n!r}")
                failed = True
            else:
                print(f"[PASS] {rel} has {n}")
    if failed:
        sys.exit(1)
    print("\nUI static checklist passed (manual browser walkthrough still recommended).")


if __name__ == "__main__":
    main()
