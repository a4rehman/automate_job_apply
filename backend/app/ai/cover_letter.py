import json
from app.ai.client import ai_client
from app.ai.prompts import COVER_LETTER_SYSTEM_PROMPT
from app.core.logging_config import logger


class CoverLetterGenerator:
    @staticmethod
    async def generate(
        candidate_name: str,
        candidate_summary: str,
        candidate_skills: list[str],
        job_title: str,
        company: str,
        job_description: str,
        custom_instructions: str = "",
    ) -> str:
        """Generate a professional cover letter under 300 words."""
        skills_str = ", ".join(candidate_skills[:10])
        user_prompt = (
            f"Candidate Name: {candidate_name}\n"
            f"Candidate Summary:\n{candidate_summary[:2000]}\n"
            f"Key Skills: {skills_str}\n\n"
            f"Target Company: {company}\n"
            f"Target Role: {job_title}\n"
            f"Job Description:\n{job_description[:3000]}\n"
        )
        if custom_instructions:
            user_prompt += f"\nAdditional Instructions: {custom_instructions}"

        cover_letter = await ai_client.generate_chat_completion(
            system_prompt=COVER_LETTER_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.4,
            response_format_json=False,
        )

        # Enforce word limit
        words = cover_letter.split()
        if len(words) > 320:
            cover_letter = " ".join(words[:300]) + "\n\nSincerely,\n" + candidate_name
            logger.info("Cover letter truncated to 300 words.")

        return cover_letter.strip()


cover_letter_generator = CoverLetterGenerator()
