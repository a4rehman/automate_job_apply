import json
import re
from typing import Dict, Any, List
from app.ai.client import ai_client
from app.ai.prompts import JOB_ANALYSIS_SYSTEM_PROMPT
from app.core.logging_config import logger

class JobAnalyzer:
    @staticmethod
    async def analyze_job_description(title: str, company: str, description: str) -> Dict[str, Any]:
        """Analyze a job posting and extract structured skills, requirements, experience, and responsibilities."""
        user_prompt = (
            f"Title: {title}\n"
            f"Company: {company}\n"
            f"Job Description:\n{description[:8000]}"
        )
        
        raw_response = await ai_client.generate_chat_completion(
            system_prompt=JOB_ANALYSIS_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            response_format_json=True
        )

        try:
            data = json.loads(raw_response)
            return {
                "required_skills": data.get("required_skills", []),
                "preferred_skills": data.get("preferred_skills", []),
                "skills": list(set(data.get("required_skills", []) + data.get("preferred_skills", []))),
                "experience_years_required": float(data.get("experience_years_required", 0.0)),
                "responsibilities": data.get("responsibilities", []),
                "summary": data.get("summary", ""),
            }
        except Exception as e:
            logger.warning(f"Error parsing job analyzer response: {e}. Falling back to rule-based extraction.")
            return JobAnalyzer._fallback_extract(title, description)

    @staticmethod
    def _fallback_extract(title: str, description: str) -> Dict[str, Any]:
        tech_keywords = [
            "Python", "Machine Learning", "Deep Learning", "Generative AI", "LLM",
            "LangChain", "OpenAI API", "FastAPI", "PyTorch", "TensorFlow", "Pandas",
            "NumPy", "SQL", "Vector Databases", "RAG", "AI Agents", "Docker", "APIs",
            "PostgreSQL", "React", "TypeScript", "AWS", "GCP", "Kubernetes", "Redis"
        ]
        found = [kw for kw in tech_keywords if re.search(rf'\b{re.escape(kw)}\b', description, re.IGNORECASE)]
        
        # Estimate years of exp
        exp_match = re.search(r'(\d+)\+?\s*years?(?:\s+of)?\s+experience', description, re.IGNORECASE)
        years_exp = float(exp_match.group(1)) if exp_match else 2.0

        return {
            "required_skills": found[:6],
            "preferred_skills": found[6:],
            "skills": found,
            "experience_years_required": years_exp,
            "responsibilities": ["Develop software and AI solutions.", "Collaborate with cross-functional teams."],
            "summary": f"Opportunity for {title} at technical scale."
        }

job_analyzer = JobAnalyzer()
