from app.schemas.resume_structured import InterviewConfig


def resolve_interview_config(
    persona: str, config: InterviewConfig | None = None
) -> InterviewConfig:
    if config is not None:
        resolved = config.model_copy(deep=True)
        if persona and persona in ("tech_lead", "hr_friendly"):
            resolved.persona = persona
    else:
        resolved = InterviewConfig(persona=persona)
        if persona == "hr_friendly":
            resolved.enable_encouragement = True
            resolved.warmth = max(resolved.warmth, 4)
        elif persona == "tech_lead":
            resolved.enable_encouragement = False
            resolved.strictness = max(resolved.strictness, 3)

    if resolved.interview_mode not in ("adaptive", "standardized"):
        resolved.interview_mode = "adaptive"
    if resolved.difficulty not in ("easy", "medium", "hard"):
        resolved.difficulty = "medium"
    return resolved
