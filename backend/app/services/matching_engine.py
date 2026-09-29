import json
import re
from typing import Dict, Any, List, Tuple
from app.models.job import Job
from app.models.user import UserProfile
from app.models.resume import Skill, Resume
from app.ai.decision_engine import decision_engine, JobDecision
from app.core.config import settings
from app.core.logging_config import logger


class MatchingEngineService:
    @staticmethod
    def calculate_skills_score(user_skills: List[str], job_skills: List[str], required_skills: List[str]) -> Tuple[float, List[str], List[str]]:
        """
        Calculates skills match score (0-100), matching skills, and missing skills.

        Honesty rule: an EMPTY target is missing data, not a perfect match.
        Returning 100.0 here would inflate every scraped job that failed skill
        extraction into a high-match candidate.
        """
        if not job_skills and not required_skills:
            return 0.0, [], []

        user_skills_normalized = {s.lower().strip(): s for s in user_skills}
        target_skills = required_skills if required_skills else job_skills
        
        matching = []
        missing = []

        for skill in target_skills:
            skill_clean = skill.lower().strip()
            matched_key = next((orig for low, orig in user_skills_normalized.items() if low == skill_clean or low in skill_clean or skill_clean in low), None)
            if matched_key:
                matching.append(skill)
            else:
                missing.append(skill)

        total_target = len(target_skills)
        if total_target == 0:
            score = 100.0
        else:
            score = (len(matching) / total_target) * 100.0

        return round(min(score, 100.0), 2), matching, missing

    @staticmethod
    def calculate_role_score(target_roles: List[str], job_title: str) -> float:
        """
        Calculates role match score (0-100) based on title match.

        No declared target roles means we cannot assert any role alignment,
        so the honest score is 0.0 rather than a flattering default.
        """
        if not target_roles:
            return 0.0

        title_lower = job_title.lower()
        for role in target_roles:
            role_lower = role.lower()
            if role_lower == title_lower or role_lower in title_lower or title_lower in role_lower:
                return 100.0
        
        title_tokens = set(re.findall(r'\w+', title_lower))
        max_overlap = 0.0
        for role in target_roles:
            role_tokens = set(re.findall(r'\w+', role.lower()))
            if role_tokens:
                overlap = len(title_tokens.intersection(role_tokens)) / len(role_tokens)
                if overlap > max_overlap:
                    max_overlap = overlap

        return round(max(max_overlap * 100.0, 40.0), 2)

    @staticmethod
    def calculate_experience_score(user_years: float, required_years: float) -> float:
        """
        Calculates experience score (0-100).
        """
        if required_years <= 0.0:
            return 100.0
        if user_years >= required_years:
            return 100.0
        ratio = user_years / required_years
        return round(max(ratio * 100.0, 30.0), 2)

    @staticmethod
    def calculate_location_score(remote_preference: str, job_remote_type: str, user_locations: List[str], job_location: str) -> float:
        """
        Calculates location fit score (0-100).
        """
        pref = (remote_preference or "REMOTE").upper()
        j_remote = (job_remote_type or "REMOTE").upper()

        if pref == "ANY" or j_remote == "REMOTE" or pref == j_remote:
            return 100.0

        if user_locations and job_location:
            job_loc_lower = job_location.lower()
            for loc in user_locations:
                if loc.lower() in job_loc_lower or job_loc_lower in loc.lower():
                    return 95.0

        return 60.0

    @staticmethod
    def calculate_salary_score(user_salary_min: float, job_salary_min: float, job_salary_max: float) -> float:
        """
        Calculates salary alignment score (0-100).

        If the user has a salary expectation but the posting does not disclose
        one, we cannot claim the requirement is met: score 0.0.
        """
        if not user_salary_min or user_salary_min <= 0:
            return 100.0  # No user expectation -> neutral
        if not job_salary_max and not job_salary_min:
            return 0.0  # Discrepancy unknown -> do not auto-pass

        effective_max = job_salary_max if job_salary_max else (job_salary_min * 1.3 if job_salary_min else user_salary_min)
        if effective_max >= user_salary_min:
            return 100.0
        
        ratio = effective_max / user_salary_min
        return round(max(ratio * 100.0, 40.0), 2)

    @classmethod
    async def match_job(
        cls,
        job: Job,
        profile: UserProfile,
        user_skills: List[str],
        resume_summary: str = ""
    ) -> Dict[str, Any]:
        """
        Executes explainable 7-factor evaluation powered by Gemini Decision Engine.
        """
        # Call Gemini Decision Engine (with automatic composite confidence & schema validation)
        decision: JobDecision = await decision_engine.evaluate_job(
            job=job,
            profile=profile,
            user_skills=user_skills,
            resume_summary=resume_summary,
        )

        overall_pct = round(decision.overall_match * 100.0, 1)
        skills_pct = round(decision.skills_match * 100.0, 1)
        role_pct = round(decision.role_match * 100.0, 1)
        exp_pct = round(decision.experience_match * 100.0, 1)
        seniority_pct = round(decision.seniority_match * 100.0, 1)
        semantic_pct = round(decision.semantic_match * 100.0, 1)
        loc_pct = round(decision.location_match * 100.0, 1)
        sal_pct = round(decision.salary_match * 100.0, 1)

        recommendation = decision.decision
        if decision.decision == "HIGH_MATCH":
            recommendation = "HIGH_PRIORITY"
        elif decision.decision == "HUMAN_REVIEW":
            recommendation = "RECOMMENDED"
        else:
            recommendation = "NOT_RECOMMENDED"

        # Human-readable, evidence-based reasons (no invented claims).
        match_reasons: List[str] = []
        if decision.matched_skills:
            match_reasons.append("Matches your skills: " + ", ".join(decision.matched_skills[:5]))
        if decision.role_match >= 0.8:
            match_reasons.append("Role title aligns with your target roles.")
        if decision.experience_match >= 0.8:
            match_reasons.append("Your experience meets the stated requirement.")
        if decision.semantic_match <= 0.0:
            match_reasons.append("No semantic analysis available (degraded confidence).")
        if decision.salary_match <= 0.0:
            match_reasons.append("Salary not disclosed in posting.")
        if decision.location_match <= 0.0:
            match_reasons.append("Location fit not verified from posting.")
        if not match_reasons:
            match_reasons.append("Insufficient evidence to establish a strong match.")

        return {
            "overall_score": overall_pct,
            "skills_score": skills_pct,
            "role_score": role_pct,
            "experience_score": exp_pct,
            "seniority_score": seniority_pct,
            "semantic_score": semantic_pct,
            "location_score": loc_pct,
            "salary_score": sal_pct,
            "confidence": round(decision.confidence, 2),
            "matching_skills": decision.matched_skills,
            "missing_skills": decision.missing_skills,
            "concerns": decision.concerns,
            "match_reasons": match_reasons,
            "application_method": decision.application_method,
            "decision": decision.decision,
            "requires_human_review": decision.requires_human_review,
            "reasoning": decision.reasoning_summary,
            "recommendation": recommendation,
        }


matching_engine = MatchingEngineService()

