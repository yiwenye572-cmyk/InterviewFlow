from pydantic import BaseModel, Field


class WorkItem(BaseModel):
    company: str = ""
    title: str = ""
    duration: str = ""
    description: str = ""


class ResumeStructured(BaseModel):
    name: str = "Unknown"
    years_experience: float = 0.0
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    work_history: list[WorkItem] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    summary: str = ""


class MatchLLMResult(BaseModel):
    score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    recommend_interview: bool = False


class AnswerEvaluation(BaseModel):
    need_followup: bool = False
    followup_reason: str = ""
    answer_quality: str = "adequate"
    resume_mismatch: bool = False
    off_topic: bool = False
    topic_for_next: str = ""
    notes: str = ""


class InterviewReport(BaseModel):
    job_fit_score: int = Field(ge=0, le=100)
    job_fit_summary: str
    communication_score: int = Field(ge=0, le=100)
    communication_summary: str
    risk_points: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    next_round_focus: list[str] = Field(default_factory=list)
    overall_recommendation: str = "hold"
