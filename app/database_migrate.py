from sqlalchemy import inspect, text

from app.database import engine


def _column_names(table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def _add_column_if_missing(table: str, column: str, ddl: str) -> None:
    if column in _column_names(table):
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


def migrate_db() -> None:
    """Lightweight SQLite migrations for existing demo databases."""
    _add_column_if_missing("jobs", "structured_json", "structured_json TEXT")
    _add_column_if_missing("resumes", "parse_quality", "parse_quality VARCHAR(32) DEFAULT 'good'")
    _add_column_if_missing(
        "screening_results", "dimension_scores_json", "dimension_scores_json TEXT DEFAULT '{}'"
    )
    _add_column_if_missing(
        "screening_results", "decision_summary", "decision_summary TEXT"
    )
    _add_column_if_missing(
        "screening_results", "followups_json", "followups_json TEXT DEFAULT '[]'"
    )
    _add_column_if_missing(
        "screening_results", "questions_json", "questions_json TEXT"
    )
    _add_column_if_missing(
        "screening_results", "score_flags_json", "score_flags_json TEXT DEFAULT '[]'"
    )
