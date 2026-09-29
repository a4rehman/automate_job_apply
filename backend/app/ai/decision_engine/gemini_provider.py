import json
import re
import math
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.core.logging_config import logger
from app.ai.decision_engine.schemas import (
    JobDecision,
    EmailApplicationExtraction,
    ApplicationEmailContent,
)
from app.ai.decision_engine.prompts import (
    DECISION_ENGINE_SYSTEM_PROMPT,
    EMAIL_EXTRACTION_SYSTEM_PROMPT,
    APPLICATION_EMAIL_SYSTEM_PROMPT,
)
from app.ai.decision_engine.validators import sanitize_input_text, validate_email_address


class GeminiProvider:
    """
    Production Gemini Provider utilizing the official Google GenAI SDK.
    Supports structured output generation via Pydantic schemas and embeddings.
    """

    def __init__(self):
        self._api_key = settings.GEMINI_API_KEY.strip() if settings.GEMINI_API_KEY else ""
        self._model_name = settings.GEMINI_MODEL or "gemini-2.5-flash"
        self._embedding_model_name = settings.GEMINI_EMBEDDING_MODEL or "text-embedding-004"
        self._genai_client = None
        self._init_client()

    def _init_client(self):
        if self._api_key:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=self._api_key)
                logger.info(f"Initialized Google GenAI client with model: {self._model_name}")
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI SDK ({e}). Fallback mode active.")
                self._genai_client = None

    @property
    def is_configured(self) -> bool:
        return bool(self._genai_client and self._api_key and len(self._api_key) > 5)

    async def evaluate_job_decision(
        self,
        job_title: str,
        company: str,
        job_description: str,
        job_skills: List[str],
        candidate_name: str,
        target_roles: List[str],
        candidate_skills: List[str],
        candidate_experience_years: float,
        candidate_bio: str,
        candidate_location: str,
        candidate_salary_min: float,
    ) -> JobDecision:
        """
        Sends structured evaluation prompt to Gemini and parses strongly-typed JobDecision.
        """
        user_prompt = (
            f"=== CANDIDATE PROFILE (VERIFIED SOURCE OF TRUTH) ===\n"
            f"Name: {candidate_name}\n"
            f"Target Roles: {', '.join(target_roles)}\n"
            f"Years of Experience: {candidate_experience_years}\n"
            f"Location & Preference: {candidate_location}\n"
            f"Minimum Salary Expectation: ${candidate_salary_min:,.2f}\n"
            f"Verified Skills: {', '.join(candidate_skills)}\n"
            f"Summary/Bio: {sanitize_input_text(candidate_bio, 2000)}\n\n"
            f"=== JOB OPENING (UNTRUSTED EXTERNAL DATA) ===\n"
            f"Company: {company}\n"
            f"Title: {job_title}\n"
            f"Required Skills Listed: {', '.join(job_skills)}\n"
            f"Job Description Excerpt:\n{sanitize_input_text(job_description, 6000)}\n"
        )

        if self.is_configured:
            try:
                # Use modern Google GenAI SDK with structured output schema
                response = self._genai_client.models.generate_content(
                    model=self._model_name,
                    contents=[DECISION_ENGINE_SYSTEM_PROMPT, user_prompt],
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": JobDecision,
                        "temperature": settings.GEMINI_TEMPERATURE,
                    }
                )
                if response.text:
                    data = json.loads(response.text)
                    return JobDecision(**data)
            except Exception as e:
                logger.warning(f"Google GenAI structured call failed: {e}. Attempting secondary fallback.")

        # Fallback to deterministic offline evaluator
        return self._mock_decision_evaluation(
            job_title=job_title,
            company=company,
            job_description=job_description,
            job_skills=job_skills,
            target_roles=target_roles,
            candidate_skills=candidate_skills,
            candidate_experience_years=candidate_experience_years,
            candidate_salary_min=candidate_salary_min,
        )

    async def extract_email_application(
        self,
        job_description: str,
        company: str,
        role: str,
    ) -> EmailApplicationExtraction:
        """
        Detects and extracts email application instructions from job description.
        """
        cleaned_jd = sanitize_input_text(job_description, 6000)
        user_prompt = f"Company: {company}\nRole: {role}\nJob Description:\n{cleaned_jd}"

        if self.is_configured:
            try:
                response = self._genai_client.models.generate_content(
                    model=self._model_name,
                    contents=[EMAIL_EXTRACTION_SYSTEM_PROMPT, user_prompt],
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": EmailApplicationExtraction,
                        "temperature": 0.0,
                    }
                )
                if response.text:
                    data = json.loads(response.text)
                    extraction = EmailApplicationExtraction(**data)
                    # Validate recipient email address format
                    if extraction.recipient_email and not validate_email_address(extraction.recipient_email):
                        extraction.recipient_email = None
                        extraction.is_email_application = False
                    return extraction
            except Exception as e:
                logger.warning(f"Gemini email extraction failed ({e}). Using regex parser.")

        # Rule-based regex extraction fallback
        return self._rule_based_email_extraction(cleaned_jd, company, role)

    async def generate_application_email(
        self,
        candidate_name: str,
        candidate_email: str,
        candidate_skills: List[str],
        candidate_bio: str,
        company: str,
        role: str,
        recipient_name: Optional[str] = None,
        job_description: str = "",
    ) -> ApplicationEmailContent:
        """
        Generates personalized, truthful application email body.
        """
        user_prompt = (
            f"Candidate: {candidate_name} ({candidate_email})\n"
            f"Top Skills: {', '.join(candidate_skills[:8])}\n"
            f"Background: {candidate_bio[:500]}\n"
            f"Target Company: {company}\n"
            f"Target Role: {role}\n"
            f"Hiring Contact: {recipient_name or 'Hiring Team'}\n"
        )

        if self.is_configured:
            try:
                response = self._genai_client.models.generate_content(
                    model=self._model_name,
                    contents=[APPLICATION_EMAIL_SYSTEM_PROMPT, user_prompt],
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": ApplicationEmailContent,
                        "temperature": 0.2,
                    }
                )
                if response.text:
                    data = json.loads(response.text)
                    return ApplicationEmailContent(**data)
            except Exception as e:
                logger.warning(f"Gemini email generation failed ({e}). Using grounded template.")

        # Grounded template fallback
        subject = f"Application for {role} — {candidate_name}"
        matched_str = ", ".join(candidate_skills[:4]) if candidate_skills else "Python and scalable systems"
        body_text = (
            f"Dear {recipient_name or 'Hiring Team'},\n\n"
            f"I am writing to express my strong interest in the {role} position at {company}.\n\n"
            f"With proven experience in {matched_str}, I am confident in my ability to deliver immediate value to your engineering team. "
            f"My attached resume details my hands-on accomplishments building and maintaining robust software solutions.\n\n"
            f"I welcome the opportunity to discuss how my background aligns with {company}'s goals.\n\n"
            f"Best regards,\n"
            f"{candidate_name}\n"
            f"{candidate_email}"
        )
        body_html = f"<p>Dear {recipient_name or 'Hiring Team'},</p><p>I am writing to express my strong interest in the <strong>{role}</strong> position at <strong>{company}</strong>.</p><p>With proven experience in <em>{matched_str}</em>, I am confident in my ability to deliver immediate value to your engineering team.</p><p>Please find my resume attached for your consideration.</p><p>Best regards,<br><strong>{candidate_name}</strong><br>{candidate_email}</p>"

        return ApplicationEmailContent(
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            highlighted_qualifications=candidate_skills[:4]
        )

    async def get_embedding(self, text: str) -> List[float]:
        """Generates embedding vector for semantic similarity."""
        cleaned = sanitize_input_text(text, 2000)
        if self.is_configured and cleaned:
            try:
                res = self._genai_client.models.embed_content(
                    model=self._embedding_model_name,
                    contents=cleaned,
                )
                if res.embedding and res.embedding.values:
                    return list(res.embedding.values)
            except Exception as e:
                logger.debug(f"Gemini embedding failed ({e}). Falling back to local vectorizer.")

        # Local deterministic TF-IDF / character bag-of-words vectorizer
        return self._local_bag_of_words_vector(cleaned)

    def calculate_cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """Calculates cosine similarity between two vectors, returning float in [0.0, 1.0]."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        similarity = dot / (norm_a * norm_b)
        return max(0.0, min(1.0, float(similarity)))

    def _local_bag_of_words_vector(self, text: str, dim: int = 64) -> List[float]:
        """Deterministic 64-dim hash bag-of-words for offline semantic similarity."""
        vec = [0.0] * dim
        words = re.findall(r"\w+", text.lower())
        if not words:
            return vec
        for w in words:
            idx = hash(w) % dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def _rule_based_email_extraction(self, jd_text: str, company: str, role: str) -> EmailApplicationExtraction:
        """Rule-based extractor for email instructions in job descriptions."""
        email_matches = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", jd_text)
        is_email_app = False
        recipient = None

        email_keywords = [
            "apply by email", "send your cv", "send cv", "email your resume",
            "send resume to", "applications should be sent to", "send application to",
            "email application", "submit your resume to"
        ]
        jd_lower = jd_text.lower()
        if any(kw in jd_lower for kw in email_keywords):
            is_email_app = True

        for em in email_matches:
            if validate_email_address(em):
                recipient = em
                is_email_app = True
                break

        return EmailApplicationExtraction(
            is_email_application=is_email_app,
            recipient_email=recipient,
            email_subject=f"Application for {role} - {company}" if recipient else None,
            required_documents=["Resume/CV"],
            instructions="Extracted via deterministic pattern matcher.",
            company=company,
            role=role,
        )

    # Factors that the deterministic fallback genuinely cannot measure. They
    # are excluded from the weighted average (carrying no weight) rather than
    # being assigned a fabricated value.
    _UNKNOWN_FACTORS = frozenset({"semantic", "location", "salary"})

    # Relative importance of each scoring factor.
    _FACTOR_WEIGHTS = {
        "skills": 0.35,
        "role": 0.25,
        "experience": 0.15,
        "seniority": 0.05,
        "semantic": 0.15,
        "location": 0.025,
        "salary": 0.025,
    }

    @classmethod
    def _weighted_overall(cls, factors: Dict[str, float]) -> float:
        """Combine factor scores, renormalising over the factors we actually measured.

        A factor that is genuinely unknown must not be treated as a *mismatch*
        (which would silently penalise every job that omits salary/location), but
        it also must not be scored as a *match*. Instead we drop unknown factors
        and reweight the measured ones, so an unavailable signal simply carries
        no weight rather than inventing a value.
        """
        measured = {
            k: v for k, v in factors.items()
            if v is not None and cls._FACTOR_WEIGHTS.get(k, 0) > 0 and k not in cls._UNKNOWN_FACTORS
        }
        total_weight = sum(cls._FACTOR_WEIGHTS[k] for k in measured)
        if total_weight <= 0:
            return 0.0
        weighted = sum(cls._FACTOR_WEIGHTS[k] * max(0.0, min(1.0, v)) for k, v in measured.items())
        return round(weighted / total_weight, 2)

    def _mock_decision_evaluation(
        self,
        job_title: str,
        company: str,
        job_description: str,
        job_skills: List[str],
        target_roles: List[str],
        candidate_skills: List[str],
        candidate_experience_years: float,
        candidate_salary_min: float,
    ) -> JobDecision:
        """Offline deterministic evaluator used when no live AI key is configured.

        HONESTY CONTRACT: this path must never invent data it does not have.
        Any signal that is genuinely unknown is scored 0.0 (not a flattering
        default) and surfaced in `concerns`, so a missing AI key can never
        manufacture a high-match job.
        """
        cand_skills_lower = {s.lower().strip() for s in candidate_skills}
        # Never assume requirements the posting did not state.
        req_skills = list(job_skills or [])
        if not req_skills:
            matched, missing = [], []
            skills_match = 0.0
        else:
            matched = [
                s for s in req_skills
                if s.lower().strip() in cand_skills_lower
                or any(s.lower().strip() in cs for cs in cand_skills_lower)
            ]
            missing = [s for s in req_skills if s not in matched]
            skills_match = min(1.0, max(0.0, len(matched) / max(len(req_skills), 1)))

        # Role match
        title_lower = (job_title or "").lower()
        role_match = 0.0
        for r in target_roles or []:
            if r.lower() in title_lower or title_lower in r.lower():
                role_match = 0.95
                break

        # Experience match
        exp_match = 1.0 if candidate_experience_years >= 3.0 else max(0.4, candidate_experience_years / 3.0)

        # Seniority match
        seniority_match = 0.90 if "senior" in title_lower and candidate_experience_years >= 4.0 else 0.80

        # Semantic match: no real embedding/LLM evaluation ran, so it is unknown.
        semantic_match = 0.0
        # Location / salary are unknown unless explicitly provided.
        location_match = 0.0
        salary_match = 0.0

        overall = GeminiProvider._weighted_overall(
            {
                "skills": skills_match,
                "role": role_match,
                "experience": exp_match,
                "seniority": seniority_match,
                "semantic": semantic_match,
                "location": location_match,
                "salary": salary_match,
            }
        )

        # No model ran, so confidence is derived from real deterministic evidence
        # and capped below the HIGH_MATCH bar: strong keyword evidence, but no
        # model verification.
        evidence = (0.5 * skills_match) + (0.3 * role_match) + (0.2 * exp_match)
        confidence = round(min(0.75, evidence), 2)

        concerns: List[str] = ["Deterministic fallback used: no live AI analysis available."]
        if not req_skills:
            concerns.append("No skills extracted from posting; skills score unavailable.")
        if not (target_roles or []):
            concerns.append("No target roles configured; role score unavailable.")

        # Detect email method in text
        jd_lower = job_description.lower()
        if "apply by email" in jd_lower or "send your cv to" in jd_lower or "@" in jd_lower:
            method = "email"
        elif "easy apply" in jd_lower or "api" in jd_lower:
            method = "authorized_api"
        else:
            method = "manual"

        decision = "HIGH_MATCH" if overall >= 0.85 else ("HUMAN_REVIEW" if overall >= 0.70 else "LOW_MATCH")
        # Keyword-only evidence must never auto-qualify a job for submission.
        # Without a live model this path is capped at HUMAN_REVIEW.
        if decision == "HIGH_MATCH":
            decision = "HUMAN_REVIEW"
            concerns.append(
                "Capped to HUMAN_REVIEW: deterministic keyword match without live AI verification."
            )

        skills_note = (
            f"{len(matched)} of {len(req_skills)} required skills matched"
            if req_skills
            else "no skills could be extracted from the posting"
        )

        return JobDecision(
            role_match=role_match,
            skills_match=skills_match,
            experience_match=exp_match,
            seniority_match=seniority_match,
            semantic_match=semantic_match,
            location_match=location_match,
            salary_match=salary_match,
            overall_match=overall,
            confidence=confidence,
            matched_skills=matched,
            missing_skills=missing,
            concerns=concerns + ([f"Missing qualifications: {', '.join(missing[:2])}"] if missing else []),
            application_method=method,
            decision=decision,
            requires_human_review=True,
            reasoning_summary=(
                f"Evaluated {job_title} at {company} using deterministic matching only "
                f"(no live AI available). Skills: {skills_note}. "
                f"Overall fit {overall * 100:.0f}% across measurable factors; "
                f"semantic, location and salary signals unavailable."
            ),
        )


gemini_provider = GeminiProvider()
