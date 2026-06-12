"""Diagnose resume parsing for a file or resume_id."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models.entities import Resume
from app.services.resume_extractor import extract_resume_structured
from app.services.resume_heuristics import build_partial_structured, guess_name_from_text


def diagnose_text(path: Path) -> int:
    text = path.read_text(encoding="utf-8")
    print(f"file: {path.name}")
    print(f"chars: {len(text)}")
    print(f"guess_name: {guess_name_from_text(text)}")
    try:
        structured = extract_resume_structured(text)
        print(f"extract: OK")
        print(f"  name: {structured.name}")
        print(f"  education: {structured.education[:2]}")
        print(f"  work_history: {len(structured.work_history)} items")
        print(f"  skills: {len(structured.skills)} items")
        return 0
    except Exception as exc:
        print(f"extract: FAIL — {exc}")
        partial = build_partial_structured(text)
        print(f"partial fallback name: {partial.name}")
        return 1


def diagnose_resume_id(resume_id: int) -> int:
    db = SessionLocal()
    try:
        resume = db.get(Resume, resume_id)
        if not resume:
            print(f"resume_id {resume_id} not found")
            return 1
        print(f"resume_id: {resume_id}")
        print(f"filename: {resume.filename}")
        print(f"parse_status: {resume.parse_status}")
        print(f"parse_quality: {resume.parse_quality}")
        print(f"chars: {len(resume.raw_text or '')}")
        if resume.structured_json:
            data = json.loads(resume.structured_json)
            print(f"stored name: {data.get('name')}")
        return diagnose_text_from_string(resume.raw_text or "")
    finally:
        db.close()


def diagnose_text_from_string(text: str) -> int:
    print(f"guess_name: {guess_name_from_text(text)}")
    try:
        structured = extract_resume_structured(text)
        print(f"extract: OK — {structured.name}")
        return 0
    except Exception as exc:
        print(f"extract: FAIL — {exc}")
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose resume structured extraction")
    parser.add_argument("--file", type=Path, help="Path to resume txt file")
    parser.add_argument("--resume-id", type=int, help="Resume id in database")
    args = parser.parse_args()

    if args.resume_id:
        sys.exit(diagnose_resume_id(args.resume_id))
    if args.file:
        sys.exit(diagnose_text(args.file))
    default = ROOT / "samples" / "yeyiwen_resume.txt"
    if default.exists():
        sys.exit(diagnose_text(default))
    print("Usage: python scripts/diagnose_resume.py --file JL.txt")
    sys.exit(2)


if __name__ == "__main__":
    main()
