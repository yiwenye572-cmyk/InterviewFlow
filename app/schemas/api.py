from pydantic import BaseModel, Field

from app.schemas.resume_structured import FollowupQuestion, InterviewConfig, InterviewQuestion


class JobResponse(BaseModel):
    id: int
    title: str
    filename: str
    message: str = "Job created"


class ResumeUploadResponse(BaseModel):
    job_id: int
    uploaded: list[str]
    count: int


class ScreeningResultItem(BaseModel):
    resume_id: int
    filename: str
    candidate_name: str
    parse_status: str
    parse_quality: str = "good"
    semantic_score: float
    llm_score: float
    final_score: float
    reasons: list[str]
    gaps: list[str]
    recommend_interview: bool
    can_interview: bool
    decision_summary: str | None = None
    dimension_scores: dict[str, int] = Field(default_factory=dict)
    followups: list[FollowupQuestion] = Field(default_factory=list)
    has_question_pack: bool = False
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)


class ScreeningResultsResponse(BaseModel):
    job_id: int
    results: list[ScreeningResultItem]


class ScreeningDetailResponse(BaseModel):
    job_id: int
    resume_id: int
    candidate_name: str
    parse_status: str
    parse_quality: str
    structured: dict | None = None
    screening: dict | None = None
    followups: list[FollowupQuestion] = Field(default_factory=list)
    dimension_scores: dict[str, int] = Field(default_factory=dict)
    decision_summary: str | None = None


class QuestionPackResponse(BaseModel):
    job_id: int
    resume_id: int
    questions: list[InterviewQuestion]
    cached: bool = False


class InterviewStartRequest(BaseModel):
    job_id: int
    resume_id: int
    persona: str = Field(default="tech_lead", pattern="^(tech_lead|hr_friendly)$")
    config: InterviewConfig | None = None


class InterviewStartResponse(BaseModel):
    session_id: int
    persona: str
    status: str
    interview_mode: str = "adaptive"


class InterviewMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class InterviewMessageResponse(BaseModel):
    session_id: int
    round_count: int
    phase: str = "opening"
    pending_action: str | None = None
    live_assessment: dict | None = None


class InterviewStatusResponse(BaseModel):
    session_id: int
    status: str
    phase: str
    round_count: int
    pending_action: str | None = None
    competencies_covered: list[str] = Field(default_factory=list)
    competencies_planned: list[str] = Field(default_factory=list)
    competency_status: dict[str, str] = Field(default_factory=dict)
    followup_streak: int = 0
    interview_mode: str = "adaptive"
    interview_config: dict = Field(default_factory=dict)
    question_index: int = 0


class InterviewMessagesResponse(BaseModel):
    session_id: int
    messages: list[dict[str, str]]


class ReportResponse(BaseModel):
    session_id: int
    status: str
    report: dict | None = None
    evaluations_log: list[dict] | None = None
