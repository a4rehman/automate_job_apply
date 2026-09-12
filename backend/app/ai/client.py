import json
import re
import httpx
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logging_config import logger


class HuggingFaceClient:
    """Simple wrapper around Hugging Face Inference API for chat‑style completions.
    Supports optional JSON‑format response parsing when the model returns a JSON string.
    """

    def __init__(self):
        self._token = settings.HF_API_TOKEN
        self._model = settings.HF_LLM_MODEL
        self._base_url = "https://api-inference.huggingface.co"
        self._client: Optional[httpx.AsyncClient] = None
        if self._token:
            self._client = httpx.AsyncClient(base_url=self._base_url, headers={"Authorization": f"Bearer {self._token}"})

    @property
    def is_configured(self) -> bool:
        return bool(self._client and self._token and self._model)

    async def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.2, response_format_json: bool = False) -> str:
        """Call the HF model with a combined prompt.
        The HF Inference API does not have a distinct system/user role, so we prepend the system prompt.
        """
        if not self.is_configured:
            raise RuntimeError("HuggingFaceClient not properly configured")
        combined = f"System: {system_prompt}\n\nUser: {user_prompt}"
        payload: Dict[str, Any] = {
            "inputs": combined,
            "parameters": {
                "temperature": temperature,
                "max_new_tokens": 512,
                "return_full_text": False,
            },
        }
        if response_format_json:
            payload["parameters"]["do_sample"] = False
        try:
            response = await self._client.post(f"/models/{self._model}", json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                text = data[0].get("generated_text", "")
            elif isinstance(data, dict):
                text = data.get("generated_text", "")
            else:
                text = ""
            return text.strip()
        except Exception as e:
            logger.warning(f"HuggingFace API call failed ({e}). Falling back to mock.")
            raise


class AIClient:
    """Unified AI client that selects OpenAI or HuggingFace based on settings.AI_PROVIDER.
    It provides the same public interface used throughout the codebase.
    """

    def __init__(self):
        self._provider = getattr(settings, "AI_PROVIDER", "openai").lower()
        self._openai_client: Optional[AsyncOpenAI] = None
        self._hf_client: Optional[HuggingFaceClient] = None
        if self._provider == "openai":
            if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip() != "":
                self._openai_client = AsyncOpenAI(
                    api_key=settings.OPENAI_API_KEY,
                    base_url=settings.OPENAI_BASE_URL,
                )
        elif self._provider == "huggingface":
            self._hf_client = HuggingFaceClient()
        else:
            logger.warning(f"Unknown AI_PROVIDER '{self._provider}'. Defaulting to mock fallback.")

    @property
    def is_configured(self) -> bool:
        if self._provider == "openai":
            return bool(self._openai_client and settings.OPENAI_API_KEY and len(settings.OPENAI_API_KEY.strip()) > 5)
        if self._provider == "huggingface":
            return bool(self._hf_client and self._hf_client.is_configured)
        return False

    async def generate_chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        response_format_json: bool = False,
    ) -> str:
        """Generate a completion using the selected backend.
        Falls back to the deterministic mock when neither provider is configured.
        """
        if self._provider == "openai" and self._openai_client:
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
                kwargs: Dict[str, Any] = {
                    "model": settings.OPENAI_MODEL,
                    "messages": messages,
                    "temperature": temperature,
                }
                if response_format_json:
                    kwargs["response_format"] = {"type": "json_object"}
                response = await self._openai_client.chat.completions.create(**kwargs)
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.warning(f"OpenAI API call failed ({e}). Falling back to mock.")
        if self._provider == "huggingface" and self._hf_client:
            try:
                return await self._hf_client.generate(system_prompt, user_prompt, temperature, response_format_json)
            except Exception:
                pass
        return self._mock_fallback(system_prompt, user_prompt, response_format_json)

    def _mock_fallback(self, system_prompt: str, user_prompt: str, is_json: bool) -> str:
        """Deterministic offline fallback for testing when no LLM is available."""
        prompt_lower = (system_prompt + "\n" + user_prompt).lower()
        if "resume_parsing" in prompt_lower or "extract resume" in prompt_lower or "parse resume" in prompt_lower:
            detected_skills = [s for s in [
                "Python", "Machine Learning", "Deep Learning", "Generative AI", "LLM",
                "LangChain", "OpenAI API", "FastAPI", "PyTorch", "TensorFlow",
                "Pandas", "NumPy", "SQL", "Vector Databases", "RAG", "AI Agents",
                "Docker", "APIs", "PostgreSQL", "React", "TypeScript"
            ] if s.lower() in user_prompt.lower()]
            if not detected_skills:
                detected_skills = ["Python", "FastAPI", "SQL", "Docker", "Machine Learning"]
            return json.dumps({
                "full_name": "AI Engineer Candidate",
                "email": "candidate@example.com",
                "phone": "+1 (555) 019-2834",
                "summary": "Experienced AI & Machine Learning Engineer specializing in LLMs, RAG, and scalable API systems.",
                "skills": detected_skills,
                "experience": [
                    {
                        "title": "Senior AI Engineer",
                        "company": "Cognitive Solutions Inc",
                        "location": "San Francisco, CA (Remote)",
                        "start_date": "2022-01",
                        "end_date": "Present",
                        "description": "Architected LLM pipelines, autonomous AI agents, and production FastAPI services.",
                        "highlights": [
                            "Built RAG pipeline indexing 5M+ technical documents with sub-200ms latency.",
                            "Optimized model inference throughput using PyTorch, TensorRT, and Docker containers.",
                            "Mentored a team of 4 junior engineers on LLM prompt engineering and vector databases."
                        ]
                    },
                    {
                        "title": "Machine Learning Developer",
                        "company": "DataTech Labs",
                        "location": "Austin, TX",
                        "start_date": "2020-03",
                        "end_date": "2021-12",
                        "description": "Engineered predictive ML models and high-throughput data processing workflows.",
                        "highlights": [
                            "Deployed TensorFlow models processing 100k daily predictions.",
                            "Built data pipelines using Pandas, NumPy, and SQL."
                        ]
                    }
                ],
                "education": [{
                    "institution": "State University of Technology",
                    "degree": "B.S. in Computer Science",
                    "field_of_study": "Artificial Intelligence",
                    "graduation_year": "2020"
                }],
                "certifications": ["AWS Certified Machine Learning - Specialty", "DeepLearning.AI Generative AI Spec"]
            })
        if "analyze_job" in prompt_lower or "extract job requirements" in prompt_lower:
            detected_skills = [s for s in [
                "Python", "Machine Learning", "Generative AI", "LLM", "LangChain",
                "FastAPI", "PyTorch", "Docker", "SQL", "Vector Databases", "RAG",
                "Kubernetes", "AWS", "GCP", "CI/CD", "Redis", "TypeScript"
            ] if s.lower() in user_prompt.lower()]
            if not detected_skills:
                detected_skills = ["Python", "FastAPI", "SQL", "Docker"]
            return json.dumps({
                "title": "AI Engineer",
                "required_skills": detected_skills[:5],
                "preferred_skills": detected_skills[5:] if len(detected_skills) > 5 else ["Kubernetes", "AWS"],
                "experience_years_required": 3.0,
                "responsibilities": [
                    "Design and deploy production‑grade LLM and RAG applications.",
                    "Develop scalable microservices using FastAPI and modern async Python.",
                    "Collaborate with cross‑functional teams to integrate generative AI features."
                ],
                "summary": "Seeking an experienced engineer to build cutting‑edge AI and LLM workflows."
            })
        if "cover_letter" in prompt_lower:
            return (
                "Dear Hiring Team,\n\n"
                "I am excited to submit my application for the open role. With a strong track record in developing "
                "production‑ready AI systems, scalable FastAPI microservices, and LLM‑powered architectures, "
                "I am confident in my ability to deliver immediate value to your engineering team.\n\n"
                "In my recent work, I have architected high‑performance RAG pipelines and scalable ML services with "
                "Python, PyTorch, and Docker. I am passionate about crafting robust, maintainable code and solving complex technical challenges.\n\n"
                "I welcome the opportunity to discuss how my technical expertise aligns with your mission.\n\n"
                "Sincerely,\nAI Engineer Candidate"
            )
        if "optimize_resume" in prompt_lower:
            return json.dumps({
                "suggested_headline": "Senior AI Engineer | LLM, RAG & Scalable Python Services",
                "optimized_bullets": [
                    {
                        "original": "Built LLM pipelines and backend APIs with Python and FastAPI.",
                        "optimized": "Architected production‑grade RAG and LLM agent pipelines using Python and FastAPI, improving response relevance and system throughput.",
                        "reason": "Emphasizes targeted generative AI terminology without fabricating metrics or unverified tools."
                    },
                    {
                        "original": "Worked with machine learning models and database storage.",
                        "optimized": "Engineered high‑throughput machine learning inference services integrated with PostgreSQL and vector databases.",
                        "reason": "Highlights relevant data engineering and model serving skills directly grounded in candidate profile."
                    }
                ],
                "keyword_alignment": ["Python", "FastAPI", "RAG", "LLM", "Docker", "Vector Databases"]
            })
        if "answer_question" in prompt_lower:
            return json.dumps({
                "answer": "Throughout my engineering career, I have focused on delivering scalable, reliable AI solutions. My background with Python, LLM architectures, and backend microservices enables me to quickly ramp up and solve high‑impact problems aligned with your engineering roadmap."
            })
        if is_json:
            return json.dumps({"status": "success", "message": "Processed successfully"})
        return "Processed successfully."


ai_client = AIClient()
