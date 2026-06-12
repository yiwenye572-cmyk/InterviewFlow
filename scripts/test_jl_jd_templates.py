"""Regression: Shopee JD + 叶亦雯 resume (Markdown TXT templates)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.resume_extractor import extract_resume_structured
from app.services.resume_heuristics import guess_name_from_text


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)


def main() -> None:
    jl = (ROOT / "samples" / "yeyiwen_resume.txt").read_text(encoding="utf-8")
    if len(jl) < 100:
        fail("yeyiwen_resume.txt too short")

    guessed = guess_name_from_text(jl)
    if guessed == "Unknown":
        fail(f"heuristic name failed: {guessed}")
    ok(f"guess_name={guessed}")

    try:
        structured = extract_resume_structured(jl)
    except Exception as exc:
        fail(f"extract_resume_structured: {exc}")

    if structured.name == "Unknown":
        fail("structured name is Unknown")
    ok(f"structured name={structured.name}")

    if not structured.education:
        fail("education empty")
    ok(f"education entries={len(structured.education)}")

    if len(structured.work_history) < 1:
        fail("work_history empty")
    ok(f"work_history items={len(structured.work_history)}")

    jd = (ROOT / "samples" / "shopee_jd.txt").read_text(encoding="utf-8")
    if "Shopee" not in jd and "后端" not in jd:
        fail("shopee_jd.txt content unexpected")
    ok("shopee_jd.txt fixture present")

    ok("JL/JD template regression passed")


if __name__ == "__main__":
    main()
