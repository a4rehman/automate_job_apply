from typing import Dict, Any, List, Optional
from app.core.config import settings
from app.core.logging_config import logger
from app.models.job import Job
from app.models.user import UserProfile
from app.ai.decision_engine.schemas import JobDecision, EmailApplicationExtraction
from app.ai.decision_engine.gemini_provider import gemini_provider
from app.ai.decision_engine.validators import validate_job_decision
from app.ai.decision_engine.confidence import calculate_composite_confidence


class GeminiDecisionEngine:
    """
    Central AI Decision Engine orchestrating Google Gemini structured classification,
    multi-signal composite confidence, and deterministic Python workflow rules.
    """

    def __init__(self):
        self.provider = gemini_provider

    async def evaluate_job(
        self,
        job: Job,
        profile: UserProfile,
        user_skills: List[str],
        resume_summary: str = "",
    ) -> JobDecision:
        """
        Executes end-to-end evaluation of a job against a verified candidate profile.
        """
        candidate_name = profile.full_name or "Candidate"
        target_roles = profile.target_roles or [profile.current_title or "Engineer"]
        job_skills = job.skills or job.requirements or []

        # 1. Structured Gemini Evaluation
        try:
            raw_decision = await self.provider.evaluate_job_decision(
                job_title=job.title,
                company=job.company,
                job_description=job.description,
                job_skills=job_skills,
                candidate_name=candidate_name,
                target_roles=target_roles,
                candidate_skills=user_skills,
                candidate_experience_years=float(profile.years_experience or 0.0),
                candidate_bio=resume_summary or profile.bio or "",
                candidate_location=f"{profile.city}, {profile.country} ({profile.remote_preference})",
                candidate_salary_min=float(profile.salary_min or 0.0),
            )
        except Exception as e:
            logger.error(f"Gemini structured evaluation failed: {e}. Generating safe fallback.")
            raw_decision = self.provider._mock_decision_evaluation(
                job_title=job.title,
                company=job.company,
                job_description=job.description,
                job_skills=job_skills,
                target_roles=target_roles,
                candidate_skills=user_skills,
                candidate_experience_years=float(profile.years_experience or 0.0),
                candidate_salary_min=float(profile.salary_min or 0.0),
            )

        # 2. Semantic Embedding Vector Verification
        try:
            cand_text = f"{profile.current_title}. Skills: {', '.join(user_skills[:10])}. {resume_summary[:300]}"
            job_text = f"{job.title} at {job.company}. {job.description[:400]}"
            cand_vec = await self.provider.get_embedding(cand_text)
            job_vec = await self.provider.get_embedding(job_text)
            embedding_sim = self.provider.calculate_cosine_similarity(cand_vec, job_vec)
            if embedding_sim > 0.0:
                raw_decision.semantic_match = round(embedding_sim, 2)
        except Exception as e:
            logger.debug(f"Semantic similarity vector step failed: {e}")

        # 3. Composite Confidence Fusion
        composite_conf = calculate_composite_confidence(
            model_confidence=raw_decision.confidence,
            resume_skills=user_skills,
            job_required_skills=job_skills,
            matched_skills=raw_decision.matched_skills,
            semantic_similarity=raw_decision.semantic_match,
            experience_years_candidate=float(profile.years_experience or 0.0),
            experience_years_required=float(job.experience_years_required or 0.0),
        )
        raw_decision.confidence = composite_conf

        # 4. Email Application Detection
        if raw_decision.application_method == "unknown" or "email" in job.description.lower():
            email_info = await self.provider.extract_email_application(
                job_description=job.description,
                company=job.company,
                role=job.title,
            )
            if email_info.is_email_application and email_info.recipient_email:
                raw_decision.application_method = "email"

        # 5. Deterministic Threshold Routing
        validated_decision = validate_job_decision(
            decision=raw_decision,
            high_match_threshold=settings.HIGH_MATCH_THRESHOLD,
            review_threshold=settings.REVIEW_THRESHOLD,
            min_confidence=settings.MIN_CONFIDENCE,
        )

        return validated_decision


decision_engine = GeminiDecisionEngine()
