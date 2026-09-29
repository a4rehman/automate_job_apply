from typing import List, Optional


def calculate_composite_confidence(
    model_confidence: float,
    resume_skills: List[str],
    job_required_skills: List[str],
    matched_skills: List[str],
    semantic_similarity: float,
    experience_years_candidate: float,
    experience_years_required: float,
    has_hard_disqualifier: bool = False
) -> float:
    """
    Computes grounded composite confidence combining AI signal and deterministic evidence.
    
    Weights:
    - Model self-reported confidence: 25%
    - Skills match overlap evidence: 35%
    - Semantic embedding similarity: 25%
    - Experience requirement alignment: 15%
    """
    if has_hard_disqualifier:
        return 0.10

    # 1. Skill overlap evidence
    if job_required_skills:
        skill_evidence_ratio = len(matched_skills) / max(len(job_required_skills), 1)
    else:
        skill_evidence_ratio = 1.0 if matched_skills else 0.5
    skill_evidence_ratio = min(1.0, max(0.0, skill_evidence_ratio))

    # 2. Semantic similarity normalized (0.0 to 1.0)
    semantic_ratio = min(1.0, max(0.0, semantic_similarity))

    # 3. Experience requirement check
    if experience_years_required <= 0:
        exp_ratio = 1.0
    elif experience_years_candidate >= experience_years_required:
        exp_ratio = 1.0
    else:
        exp_ratio = max(0.2, experience_years_candidate / experience_years_required)

    # 4. Model signal
    model_signal = min(1.0, max(0.0, model_confidence))

    composite = (
        (model_signal * 0.25) +
        (skill_evidence_ratio * 0.35) +
        (semantic_ratio * 0.25) +
        (exp_ratio * 0.15)
    )

    return round(min(1.0, max(0.0, composite)), 3)


def calculate_resume_evidence_score(
    matched_skills: List[str],
    candidate_skills: List[str],
    resume_text: str = ""
) -> float:
    """Calculates factual evidence grounding score based on resume text and verified skills."""
    if not candidate_skills and not resume_text:
        return 0.5
    cand_set = {s.lower().strip() for s in candidate_skills}
    text_lower = resume_text.lower()
    
    hits = 0
    total = max(len(matched_skills), 1)
    for s in matched_skills:
        s_clean = s.lower().strip()
        if s_clean in cand_set or s_clean in text_lower:
            hits += 1
            
    return round(hits / total, 3)

