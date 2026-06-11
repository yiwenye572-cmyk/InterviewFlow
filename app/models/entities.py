from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="Untitled Job")
    filename: Mapped[str] = mapped_column(String(512))
    raw_text: Mapped[str] = mapped_column(Text)
    structured_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rubric_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    resumes: Mapped[list["Resume"]] = relationship(back_populates="job")
    screenings: Mapped[list["ScreeningResult"]] = relationship(back_populates="job")
    sessions: Mapped[list["InterviewSession"]] = relationship(back_populates="job")


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    filename: Mapped[str] = mapped_column(String(512))
    raw_text: Mapped[str] = mapped_column(Text)
    parse_status: Mapped[str] = mapped_column(String(32), default="pending")
    parse_quality: Mapped[str] = mapped_column(String(32), default="good")
    structured_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessment_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    job: Mapped["Job"] = relationship(back_populates="resumes")
    screening: Mapped["ScreeningResult | None"] = relationship(
        back_populates="resume", uselist=False
    )
    sessions: Mapped[list["InterviewSession"]] = relationship(back_populates="resume")


class ScreeningResult(Base):
    __tablename__ = "screening_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), unique=True)
    semantic_score: Mapped[float] = mapped_column(Float, default=0.0)
    llm_score: Mapped[float] = mapped_column(Float, default=0.0)
    final_score: Mapped[float] = mapped_column(Float, default=0.0)
    reasons_json: Mapped[str] = mapped_column(Text, default="[]")
    gaps_json: Mapped[str] = mapped_column(Text, default="[]")
    dimension_scores_json: Mapped[str] = mapped_column(Text, default="{}")
    decision_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    followups_json: Mapped[str] = mapped_column(Text, default="[]")
    questions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_flags_json: Mapped[str] = mapped_column(Text, default="[]")
    recommend_interview: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    job: Mapped["Job"] = relationship(back_populates="screenings")
    resume: Mapped["Resume"] = relationship(back_populates="screening")


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"))
    persona: Mapped[str] = mapped_column(String(64), default="tech_lead")
    status: Mapped[str] = mapped_column(String(32), default="active")
    persona_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    running_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    round_count: Mapped[int] = mapped_column(Integer, default=0)
    topics_covered_json: Mapped[str] = mapped_column(Text, default="[]")
    pending_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_evaluation_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    phase: Mapped[str] = mapped_column(String(32), default="opening")
    risk_notes_json: Mapped[str] = mapped_column(Text, default="[]")
    evaluations_log_json: Mapped[str] = mapped_column(Text, default="[]")
    competencies_planned_json: Mapped[str] = mapped_column(Text, default="[]")
    competencies_covered_json: Mapped[str] = mapped_column(Text, default="[]")
    followup_queue_json: Mapped[str] = mapped_column(Text, default="[]")
    live_assessment_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_plan_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    followup_streak: Mapped[int] = mapped_column(Integer, default=0)
    current_topic: Mapped[str | None] = mapped_column(String(512), nullable=True)
    competency_status_json: Mapped[str] = mapped_column(Text, default="{}")
    interview_config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_queue_json: Mapped[str] = mapped_column(Text, default="[]")
    question_index: Mapped[int] = mapped_column(Integer, default=0)
    encouraged_this_round: Mapped[bool] = mapped_column(default=False)
    candidate_feedback_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    job: Mapped["Job"] = relationship(back_populates="sessions")
    resume: Mapped["Resume"] = relationship(back_populates="sessions")
    messages: Mapped[list["InterviewMessage"]] = relationship(
        back_populates="session", order_by="InterviewMessage.id"
    )


class InterviewMessage(Base):
    __tablename__ = "interview_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id"))
    role: Mapped[str] = mapped_column(String(32))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["InterviewSession"] = relationship(back_populates="messages")
