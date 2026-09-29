import re
from typing import Optional
from app.ai.decision_engine.schemas import JobDecision, EmailApplicationExtraction
from app.core.logging_config import logger

EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
)

# Common disposable or invalid domains/addresses to flag
SUSPICIOUS_DOMAINS = {"example.com", "test.com", "localhost", "sample.org", "fake.com"}


def validate_email_address(email: Optional[str]) -> bool:
    """Validates an extracted email address with RFC syntax and domain checks."""
    if not email or not isinstance(email, str):
        return False
    email_clean = email.strip().lower()
    if len(email_clean) < 5 or len(email_clean) > 254:
        return False
    if not EMAIL_REGEX.match(email_clean):
        return False
    domain = email_clean.split("@")[-1]
    if domain in SUSPICIOUS_DOMAINS:
        logger.warning(f"Extracted email domain '{domain}' is in suspicious domains list.")
        return False
    return True


def sanitize_input_text(text: Optional[str], max_len: int = 15000, *, max_length: int | None = None) -> str:
    """Sanitizes untrusted job description or candidate text."""
    if max_length is not None:
        max_len = max_length
    if not text:
        return ""
    # Strip HTML script/style tags and control chars
    cleaned = re.sub(r"<(script|style).*?>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", cleaned)
    return cleaned[:max_len].strip()


def validate_score_bounds(score: float) -> float:
    """Clamps a floating point score between 0.0 and 1.0."""
    try:
        val = float(score)
        return max(0.0, min(1.0, val))
    except (ValueError, TypeError):
        return 0.0


def enforce_deterministic_rule_overrides(
    decision: JobDecision,
    high_match_threshold: float = 0.85,
    review_threshold: float = 0.70,
    min_confidence: float = 0.60
) -> JobDecision:
    """Explicit alias for validate_job_decision applying strict rule overrides."""
    if decision.confidence < min_confidence:
        decision.decision = "HUMAN_REVIEW"
        decision.requires_human_review = True
        if not any("confidence" in c.lower() for c in decision.concerns):
            decision.concerns.append(f"Low model confidence ({decision.confidence:.2f} < {min_confidence:.2f})")
        return decision
    return validate_job_decision(
        decision=decision,
        high_match_threshold=high_match_threshold,
        review_threshold=review_threshold,
        min_confidence=min_confidence,
    )


def validate_job_decision(
    decision: JobDecision,
    high_match_threshold: float = 0.85,
    review_threshold: float = 0.70,
    min_confidence: float = 0.60
) -> JobDecision:
    """
    Applies deterministic Python rule validation to Gemini structured output.
    Ensures model-reported decision matches mathematical thresholds.
    """
    # Deterministic rule alignment
    if decision.overall_match >= high_match_threshold and decision.confidence >= min_confidence:
        deterministic_decision = "HIGH_MATCH"
    elif decision.overall_match >= review_threshold:
        deterministic_decision = "HUMAN_REVIEW"
    else:
        deterministic_decision = "LOW_MATCH"

    # Python rules have final authority over model recommendation
    if decision.decision != deterministic_decision:
        logger.info(
            f"Overriding model decision '{decision.decision}' with deterministic decision '{deterministic_decision}' "
            f"(Score: {decision.overall_match:.2f}, Conf: {decision.confidence:.2f})"
        )
        decision.decision = deterministic_decision

    # High match without human approval is only permitted if explicitly safe
    if decision.decision in ("HIGH_MATCH", "HUMAN_REVIEW"):
        decision.requires_human_review = True
    else:
        decision.requires_human_review = False

    return decision
