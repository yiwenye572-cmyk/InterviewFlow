from pydantic import BaseModel, Field


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
    semantic_score: float
    llm_score: float
    final_score: float
    reasons: list[str]
    gaps: list[str]
    recommend_interview: bool
    can_interview: bool


class ScreeningResultsResponse(BaseModel):
    job_id: int
    results: list[ScreeningResultItem]


class InterviewStartRequest(BaseModel):
    job_id: int
    resume_id: int
    persona: str = Field(default="tech_lead", pattern="^(tech_lead|hr_friendly)$")


class InterviewStartResponse(BaseModel):
    session_id: int
    persona: str
    status: str


class InterviewMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class ReportResponse(BaseModel):
    session_id: int
    status: str
    report: dict | None = None
