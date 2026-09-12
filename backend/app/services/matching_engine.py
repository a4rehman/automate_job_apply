import json
import re
from typing import Dict, Any, List, Tuple
from app.models.job import Job
from app.models.user import UserProfile
from app.models.resume import Skill, Resume
from app.ai.client import ai_client
from app.ai.prompts import MATCHING_ANALYSIS_SYSTEM_PROMPT
from app.core.logging_config import logger

class MatchingEngineService:
    @staticmethod
    def calculate_skills_score(user_skills: List[str], job_skills: List[str], required_skills: List[str]) -> Tuple[float, List[str], List[str]]:
        """
        Calculates skills match score (0-100), matching skills, and missing skills.
        """
        if not job_skills and not required_skills:
            return 85.0, user_skills[:5], []

        user_skills_normalized = {s.lower().strip(): s for s in user_skills}
        target_skills = required_skills if required_skills else job_skills
        
        matching = []
        missing = []

        for skill in target_skills:
            skill_clean = skill.lower().strip()
            # Direct match or substring containment
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
        """
        if not target_roles:
            return 80.0

        title_lower = job_title.lower()
        
        # Check exact or strong keyword overlap
        for role in target_roles:
            role_lower = role.lower()
            if role_lower == title_lower or role_lower in title_lower or title_lower in role_lower:
                return 100.0
        
        # Word token overlap
        title_tokens = set(re.findall(r'\w+', title_lower))
        max_overlap = 0.0
        for role in target_roles:
            role_tokens = set(re.findall(r'\w+', role.lower()))
            if role_tokens:
                overlap = len(title_tokens.intersection(role_tokens)) / len(role_tokens)
                if overlap > max_overlap:
                    max_overlap = overlap

        return round(max_overlap * 100.0, 2)

    @staticmethod
    def calculate_experience_score(user_years: float, required_years: float) -> float:
        """
        Calculates experience score (0-100).
        """
        if required_years <= 0.0:
            return 100.0
        if user_years >= required_years:
            return 100.0
        
        # Gradual penalty for missing years
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

        # Check location strings
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
        """
        if not user_salary_min or user_salary_min <= 0:
            return 100.0
        if not job_salary_max and not job_salary_min:
            return 90.0 # Unknown job salary treated favorably

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
        Executes the full weighted 6-factor matching calculation.
        """
        # 1. Skills Match (35%)
        skills_score, matching_skills, missing_skills = cls.calculate_skills_score(
            user_skills=user_skills,
            job_skills=job.skills or [],
            required_skills=job.requirements or []
        )

        # 2. Role Match (25%)
        role_score = cls.calculate_role_score(
            target_roles=profile.target_roles or [],
            job_title=job.title
        )

        # 3. Experience Match (15%)
        exp_score = cls.calculate_experience_score(
            user_years=profile.years_experience or 0.0,
            required_years=job.experience_years_required or 0.0
        )

        # 4. Semantic Similarity (15%)
        semantic_score = await cls._calculate_semantic_similarity(
            resume_summary=resume_summary or profile.bio or f"{profile.current_title} with skills {', '.join(user_skills[:8])}",
            job_title=job.title,
            job_description=job.description
        )

        # 5. Location Preference (5%)
        location_score = cls.calculate_location_score(
            remote_preference=profile.remote_preference,
            job_remote_type=job.remote_type,
            user_locations=profile.preferred_locations or [],
            job_location=job.location
        )

        # 6. Salary Preference (5%)
        salary_score = cls.calculate_salary_score(
            user_salary_min=profile.salary_min,
            job_salary_min=job.salary_min or 0.0,
            job_salary_max=job.salary_max or 0.0
        )

        # Calculate Final Weighted Score
        final_score = (
            skills_score * 0.35 +
            role_score * 0.25 +
            exp_score * 0.15 +
            semantic_score * 0.15 +
            location_score * 0.05 +
            salary_score * 0.05
        )
        final_score = round(min(max(final_score, 0.0), 100.0), 1)

        # Recommendation Category
        if final_score >= 90.0:
            recommendation = "HIGH_PRIORITY"
        elif final_score >= 75.0:
            recommendation = "RECOMMENDED"
        else:
            recommendation = "NOT_RECOMMENDED"

        # Generate reasoning summary
        reasoning = cls._generate_reasoning(
            final_score=final_score,
            role_title=job.title,
            matching_skills=matching_skills,
            missing_skills=missing_skills,
            exp_score=exp_score
        )

        return {
            "overall_score": final_score,
            "skills_score": skills_score,
            "role_score": role_score,
            "experience_score": exp_score,
            "semantic_score": semantic_score,
            "location_score": location_score,
            "salary_score": salary_score,
            "matching_skills": matching_skills,
            "missing_skills": missing_skills,
            "reasoning": reasoning,
            "recommendation": recommendation,
        }

    @staticmethod
    async def _calculate_semantic_similarity(resume_summary: str, job_title: str, job_description: str) -> float:
        """Evaluate semantic relevance using AI client."""
        user_prompt = (
            f"Candidate Summary: {resume_summary}\n\n"
            f"Target Job Title: {job_title}\n"
            f"Job Description Excerpt: {job_description[:1500]}"
        )
        try:
            raw = await ai_client.generate_chat_completion(
                system_prompt=MATCHING_ANALYSIS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.1,
                response_format_json=True
            )
            data = json.loads(raw)
            return float(data.get("semantic_score", 85.0))
        except Exception:
            return 85.0

    @staticmethod
    def _generate_reasoning(
        final_score: float,
        role_title: str,
        matching_skills: List[str],
        missing_skills: List[str],
        exp_score: float
    ) -> str:
        matches_str = ", ".join(matching_skills[:5]) if matching_skills else "General technical qualifications"
        missing_str = ", ".join(missing_skills[:3]) if missing_skills else "None"
        
        if final_score >= 90:
            return f"Outstanding match for {role_title}. Strong alignment in {matches_str}. Missing competencies ({missing_str}) are minor."
        elif final_score >= 75:
            return f"Strong match for {role_title}. Matches primary core requirements ({matches_str}). Recommend highlighting transferrable experience for {missing_str}."
        else:
            return f"Moderate to low match for {role_title}. Key skill gaps identified in {missing_str}."

matching_engine = MatchingEngineService()
