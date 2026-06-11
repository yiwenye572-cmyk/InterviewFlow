from pydantic import BaseModel, Field


class WorkItem(BaseModel):
    company: str = ""
    title: str = ""
    duration: str = ""
    description: str = ""


class ContactInfo(BaseModel):
    phone: str = ""
    email: str = ""


class ResumeStructured(BaseModel):
    name: str = "Unknown"
    years_experience: float = 0.0
    skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    work_history: list[WorkItem] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    summary: str = ""
    contact: ContactInfo | None = None
    expected_salary: str | None = None
    interview_feedback: list[str] = Field(default_factory=list)


class JDStructured(BaseModel):
    title: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    min_years: float = 0.0
    responsibilities: list[str] = Field(default_factory=list)
    hard_filters: list[str] = Field(default_factory=list)


class MatchLLMResult(BaseModel):
    score: int = Field(ge=0, le=100)
    dimension_scores: dict[str, int] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    recommend_interview: bool = False
    decision_summary: str = ""


class FollowupQuestion(BaseModel):
    question: str
    target_ambiguity: str = ""
    probe_intent: str = ""
    difficulty: str = "medium"


class FollowupPack(BaseModel):
    items: list[FollowupQuestion] = Field(default_factory=list)


class InterviewQuestion(BaseModel):
    question: str
    competency: str = ""
    difficulty: str = "medium"
    rubric: str = ""
    category: str = "technical"


class QuestionPack(BaseModel):
    items: list[InterviewQuestion] = Field(default_factory=list)


class AnswerEvaluation(BaseModel):
    need_followup: bool = False
    followup_reason: str = ""
    answer_quality: str = "adequate"
    resume_mismatch: bool = False
    off_topic: bool = False
    topic_for_next: str = ""
    notes: str = ""
    competency_signal: str = ""
    partial_score: int = Field(default=60, ge=0, le=100)
    communication_signal: str = "clear"
    evidence_density: str = "medium"


class ScoreReviewResult(BaseModel):
    adjusted_partial_score: int = Field(ge=0, le=100)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    calibration_notes: str = ""
    evidence_quotes: list[str] = Field(default_factory=list)
    adjusted_answer_quality: str = "adequate"
    adjusted_communication_signal: str = "clear"


class RubricProfile(BaseModel):
    criteria: list[dict] = Field(default_factory=list)
    summary: str = ""


class JobTemplate(BaseModel):
    id: str
    label: str = ""
    default_competencies: list[str] = Field(default_factory=list)
    phase_strategy: list[str] = Field(default_factory=list)
    match_dimension_labels: dict[str, str] = Field(default_factory=dict)


class PersonaProfile(BaseModel):
    role_title: str = "Interviewer"
    tone_description: str = ""
    focus_areas: list[str] = Field(default_factory=list)
    question_style: str = ""
    system_prompt_block: str = ""


class TopicPlan(BaseModel):
    phase: str = "technical"
    next_topic: str = ""
    competency_target: str = ""
    rationale: str = ""
    should_close: bool = False


class LiveAssessment(BaseModel):
    round_count: int = 0
    current_phase: str = "opening"
    provisional_job_fit: int = Field(default=60, ge=0, le=100)
    provisional_communication: int = Field(default=60, ge=0, le=100)
    observed_strengths: list[str] = Field(default_factory=list)
    observed_risks: list[str] = Field(default_factory=list)
    last_updated: str = ""
    score_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    calibration_summary: str = ""


class InterviewReport(BaseModel):
    job_fit_score: int = Field(ge=0, le=100)
    job_fit_summary: str
    communication_score: int = Field(ge=0, le=100)
    communication_summary: str
    risk_points: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    next_round_focus: list[str] = Field(default_factory=list)
    overall_recommendation: str = "hold"
    dimension_scores: dict[str, int] = Field(default_factory=dict)
    dimension_summaries: dict[str, str] = Field(default_factory=dict)
    hiring_decision_rationale: str = ""
    live_snapshot: dict | None = None
    score_confidence: float = Field(default=0.7, ge=0.0, le=1.0)
