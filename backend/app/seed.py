import hashlib
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import AsyncSessionLocal
from app.core.security import get_password_hash
from app.core.logging_config import logger
from app.models.user import User, UserProfile
from app.models.resume import Skill
from app.models.job import Job, JobMatch, JobStatus
from app.models.application import Application, ApplicationStatus
from app.models.automation import AutomationSettings
from app.models.notification import Notification, NotificationLevel


async def seed_database():
    """Seed database with a demo AI Engineer profile and realistic sample jobs."""
    async with AsyncSessionLocal() as db:
        from sqlalchemy import select

        # Check if demo user already exists
        existing = await db.execute(select(User).where(User.email == "demo@jobagent.ai"))
        if existing.scalar_one_or_none():
            logger.info("Database already seeded.")
            return

        # Create demo user
        user = User(
            email="demo@jobagent.ai",
            hashed_password=get_password_hash("demo1234"),
            is_active=True,
        )
        db.add(user)
        await db.flush()

        # Create AI Engineer profile
        profile = UserProfile(
            user_id=user.id,
            full_name="Alex Johnson",
            phone="+1 (555) 019-2834",
            city="San Francisco",
            country="United States",
            linkedin_url="https://linkedin.com/in/alexjohnson-ai",
            github_url="https://github.com/alexjohnson-ai",
            portfolio_url="https://alexjohnson.dev",
            current_title="AI Engineer",
            years_experience=5.0,
            target_roles=[
                "AI Engineer", "Machine Learning Engineer", "Generative AI Engineer",
                "Data Scientist", "Applied AI Engineer", "NLP Engineer",
                "LLM Engineer", "AI Developer", "Python Developer", "MLOps Engineer",
            ],
            preferred_industries=["Technology", "AI/ML", "SaaS", "FinTech", "HealthTech"],
            preferred_locations=["San Francisco", "New York", "Remote"],
            remote_preference="REMOTE",
            salary_min=150000,
            salary_currency="USD",
            employment_types=["FULL_TIME", "CONTRACT"],
            bio=(
                "Senior AI Engineer with 5+ years building production LLM pipelines, "
                "RAG systems, and scalable FastAPI microservices. Expert in Python, PyTorch, "
                "and cloud-native AI deployments."
            ),
        )
        db.add(profile)

        # Skills
        demo_skills = [
            ("Python", "LANGUAGES", 5, 5.0),
            ("Machine Learning", "ML_AI", 5, 4.0),
            ("Deep Learning", "ML_AI", 4, 3.0),
            ("Generative AI", "ML_AI", 5, 2.0),
            ("LLM", "ML_AI", 5, 2.5),
            ("LangChain", "FRAMEWORKS", 4, 1.5),
            ("OpenAI API", "ML_AI", 5, 2.0),
            ("FastAPI", "FRAMEWORKS", 5, 3.0),
            ("PyTorch", "ML_AI", 4, 3.0),
            ("TensorFlow", "ML_AI", 3, 2.0),
            ("Pandas", "TOOLS", 5, 5.0),
            ("NumPy", "TOOLS", 5, 5.0),
            ("SQL", "LANGUAGES", 4, 4.0),
            ("Vector Databases", "TOOLS", 4, 1.5),
            ("RAG", "ML_AI", 5, 2.0),
            ("AI Agents", "ML_AI", 4, 1.0),
            ("Docker", "TOOLS", 4, 3.0),
            ("APIs", "TECHNICAL", 5, 5.0),
            ("PostgreSQL", "TOOLS", 4, 3.0),
        ]
        for name, cat, prof, yrs in demo_skills:
            db.add(Skill(user_id=user.id, name=name, category=cat, proficiency=prof, years_experience=yrs))

        # Automation settings
        db.add(AutomationSettings(user_id=user.id))

        # Sample jobs
        sample_jobs = [
            {
                "title": "Senior AI Engineer",
                "company": "Anthropic",
                "location": "San Francisco, CA (Remote)",
                "remote_type": "REMOTE",
                "description": (
                    "We are looking for a Senior AI Engineer to help build next-generation LLM systems. "
                    "You will design and implement production-grade AI pipelines, develop RAG architectures, "
                    "and work on autonomous AI agent frameworks. Requirements: Python, PyTorch, LLM experience, "
                    "RAG systems, FastAPI or similar frameworks. 5+ years of engineering experience."
                ),
                "requirements": ["Python", "PyTorch", "LLM", "RAG", "FastAPI"],
                "preferred_skills": ["Kubernetes", "AWS", "Rust"],
                "skills": ["Python", "PyTorch", "LLM", "RAG", "FastAPI", "Docker", "AI Agents"],
                "salary_min": 180000, "salary_max": 280000,
                "experience_years_required": 5.0,
                "job_url": "https://example.com/jobs/anthropic-ai-engineer",
            },
            {
                "title": "Machine Learning Engineer",
                "company": "OpenAI",
                "location": "San Francisco, CA",
                "remote_type": "HYBRID",
                "description": (
                    "Join OpenAI as a Machine Learning Engineer focused on training and deploying large language models. "
                    "Responsibilities include building scalable training infrastructure, optimizing model performance, "
                    "and developing evaluation frameworks. Requirements: Python, Deep Learning, PyTorch/TensorFlow, "
                    "distributed training, strong math and statistics background."
                ),
                "requirements": ["Python", "Deep Learning", "PyTorch", "TensorFlow"],
                "preferred_skills": ["CUDA", "Distributed Systems", "C++"],
                "skills": ["Python", "Deep Learning", "PyTorch", "TensorFlow", "Machine Learning"],
                "salary_min": 200000, "salary_max": 350000,
                "experience_years_required": 4.0,
                "job_url": "https://example.com/jobs/openai-ml-engineer",
            },
            {
                "title": "Generative AI Developer",
                "company": "Vercel AI Labs",
                "location": "Remote (Global)",
                "remote_type": "REMOTE",
                "description": (
                    "Build AI-powered developer tools and SDK features. Integrate LLMs into production products, "
                    "develop generative AI features for web applications, and create AI-assisted coding tools. "
                    "Requirements: Python, TypeScript, LLM APIs, LangChain, vector databases. "
                    "Experience with RAG and prompt engineering required."
                ),
                "requirements": ["Python", "TypeScript", "LLM", "LangChain", "Vector Databases"],
                "preferred_skills": ["Next.js", "Vercel", "Streaming APIs"],
                "skills": ["Python", "TypeScript", "LLM", "LangChain", "Vector Databases", "RAG"],
                "salary_min": 160000, "salary_max": 240000,
                "experience_years_required": 3.0,
                "job_url": "https://example.com/jobs/vercel-gen-ai",
            },
            {
                "title": "Data Scientist - NLP",
                "company": "Spotify",
                "location": "New York, NY",
                "remote_type": "HYBRID",
                "description": (
                    "Apply NLP and ML techniques to improve music recommendations and search. "
                    "Work with large-scale text and audio data. Build and deploy models using Python, "
                    "Pandas, scikit-learn, and deep learning frameworks. 3+ years experience required."
                ),
                "requirements": ["Python", "Pandas", "Machine Learning", "NLP"],
                "preferred_skills": ["Spark", "Scala", "Audio Processing"],
                "skills": ["Python", "Pandas", "Machine Learning", "NLP", "Deep Learning", "SQL"],
                "salary_min": 140000, "salary_max": 200000,
                "experience_years_required": 3.0,
                "job_url": "https://example.com/jobs/spotify-nlp",
            },
            {
                "title": "Frontend React Developer",
                "company": "Stripe",
                "location": "Remote (US)",
                "remote_type": "REMOTE",
                "description": (
                    "Build beautiful, performant payment interfaces using React, TypeScript, and modern CSS. "
                    "Work on Stripe Dashboard and Checkout experiences. 4+ years frontend experience required. "
                    "Strong understanding of web performance, accessibility, and design systems."
                ),
                "requirements": ["React", "TypeScript", "CSS", "HTML"],
                "preferred_skills": ["Next.js", "GraphQL", "Figma"],
                "skills": ["React", "TypeScript", "CSS", "HTML", "JavaScript"],
                "salary_min": 170000, "salary_max": 250000,
                "experience_years_required": 4.0,
                "job_url": "https://example.com/jobs/stripe-frontend",
            },
        ]

        now = datetime.now(timezone.utc)
        for i, j in enumerate(sample_jobs):
            desc = j["description"]
            desc_hash = hashlib.sha256(
                f"{j['title'].lower()}|{j['company'].lower()}|{desc[:1000]}".encode()
            ).hexdigest()
            job = Job(
                source_name="SEED_DATA",
                title=j["title"],
                company=j["company"],
                location=j["location"],
                remote_type=j["remote_type"],
                employment_type="FULL_TIME",
                salary_min=j.get("salary_min"),
                salary_max=j.get("salary_max"),
                currency="USD",
                description=desc,
                description_hash=desc_hash,
                requirements=j.get("requirements", []),
                preferred_skills=j.get("preferred_skills", []),
                skills=j.get("skills", []),
                experience_years_required=j.get("experience_years_required", 2.0),
                job_url=j.get("job_url", ""),
                posted_date=now - timedelta(hours=i * 6),
                detected_date=now - timedelta(hours=i * 2),
                status=JobStatus.NEW,
            )
            db.add(job)

        await db.commit()

        # Welcome notification
        db.add(Notification(
            user_id=user.id,
            title="👋 Welcome to AI Job Agent!",
            message="Your AI-powered job automation agent is ready. Upload your resume and configure your profile to get started.",
            level=NotificationLevel.INFO,
            link="/profile",
        ))
        await db.commit()

        logger.info("✅ Database seeded with demo AI Engineer profile and 5 sample jobs.")
