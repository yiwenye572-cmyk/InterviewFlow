from pydantic import AliasChoices, BaseModel, Field

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


class ResumeListItem(BaseModel):
    resume_id: int
    filename: str
    candidate_name: str = "Unknown"
    parse_status: str = "pending"
    screened: bool = False
    final_score: float | None = None


class JobResumeListResponse(BaseModel):
    job_id: int
    resumes: list[ResumeListItem] = Field(default_factory=list)


class ScreenRequest(BaseModel):
    resume_ids: list[int] | None = None
    async_mode: bool = Field(default=True, validation_alias=AliasChoices("async", "async_mode"))


class ScreenBatchItem(BaseModel):
    resume_id: int
    filename: str
    status: str
    error: str | None = None


class ScreenBatchStatusResponse(BaseModel):
    batch_id: str
    job_id: int
    total: int
    completed: int
    failed: int
    status: str
    items: list[ScreenBatchItem] = Field(default_factory=list)


class ScreenBatchStartResponse(BaseModel):
    batch_id: str
    job_id: int
    total: int
    message: str = "Screening batch started"


class UpcomingQuestionPreview(BaseModel):
    question: str
    competency: str = ""
    difficulty: str = ""
    category: str = ""


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
    score_flags: list[str] = Field(default_factory=list)


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


class VoiceTurnResponse(BaseModel):
    session_id: int
    transcript: str
    assistant_text: str
    audio_base64: str
    audio_mime: str = "audio/mpeg"
    round_count: int
    phase: str = "opening"
    pending_action: str | None = None
    live_assessment: dict | None = None


class InterviewStatusResponse(BaseModel):
    session_id: int
    job_id: int
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
    current_topic: str = ""
    followup_queue: list[str] = Field(default_factory=list)
    upcoming_questions: list[UpcomingQuestionPreview] = Field(default_factory=list)


class InterviewMessagesResponse(BaseModel):
    session_id: int
    messages: list[dict[str, str]]


class ReportResponse(BaseModel):
    session_id: int
    job_id: int
    status: str
    report: dict | None = None
    evaluations_log: list[dict] | None = None
    score_timeline: list[dict] | None = None
    candidate_feedback: dict | None = None


class EndInterviewRequest(BaseModel):
    async_mode: bool = Field(
        default=True, validation_alias=AliasChoices("async", "async_mode")
    )


class ReportGenerationStatusResponse(BaseModel):
    session_id: int
    job_id: int
    status: str
    stage: str
    progress: int
    message: str
    error: str | None = None


class CandidateFeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class CandidateFeedbackResponse(BaseModel):
    session_id: int
    submitted: bool = True
    feedback: dict


class JobListItem(BaseModel):
    id: int
    title: str
    filename: str
    created_at: str | None = None
    resume_count: int = 0
    interview_count: int = 0
    completed_interview_count: int = 0
    jd_summary: str = ""
    has_structured: bool = False


class InterviewSummaryItem(BaseModel):
    session_id: int
    resume_id: int
    candidate_name: str
    persona: str
    interview_mode: str = "adaptive"
    status: str
    round_count: int = 0
    created_at: str | None = None
    report_summary: str | None = None
    job_fit_score: int | None = None
    communication_score: int | None = None
    overall_recommendation: str | None = None


class JobOverviewResponse(BaseModel):
    job: JobListItem
    jd_summary: str = ""
    jd_structured: dict | None = None
    interviews: list[InterviewSummaryItem] = Field(default_factory=list)


class JobListResponse(BaseModel):
    jobs: list[JobListItem] = Field(default_factory=list)
