import io
import re
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

# Optional pypdf import for real PDF resume parsing
try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


# ==============================================================================
# --- Page Configuration ---
# ==============================================================================
st.set_page_config(
    page_title="AI Job Application Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ==============================================================================
# --- Premium Dark Theme & Responsive CSS ---
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    :root {
        --bg-primary: #0a0a0f;
        --bg-secondary: #12121a;
        --bg-card: #16161f;
        --bg-card-hover: #1c1c28;
        --border: #2a2a3a;
        --accent: #6366f1;
        --accent-light: #818cf8;
        --accent-glow: rgba(99, 102, 241, 0.15);
        --green: #22c55e;
        --green-bg: rgba(34, 197, 94, 0.1);
        --yellow: #eab308;
        --yellow-bg: rgba(234, 179, 8, 0.1);
        --red: #ef4444;
        --red-bg: rgba(239, 68, 68, 0.1);
        --blue: #3b82f6;
        --blue-bg: rgba(59, 130, 246, 0.1);
        --orange: #f97316;
        --text-primary: #f1f5f9;
        --text-secondary: #94a3b8;
        --text-muted: #64748b;
    }

    .stApp {
        background: var(--bg-primary) !important;
        font-family: 'Inter', sans-serif;
    }
    .stApp > header { background: transparent !important; }

    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: var(--bg-secondary) !important;
        border-right: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown li,
    section[data-testid="stSidebar"] label {
        color: var(--text-secondary) !important;
    }

    /* KPI Metrics */
    div[data-testid="stMetric"] {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 16px 20px;
        transition: all 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        border-color: var(--accent);
        box-shadow: 0 0 20px var(--accent-glow);
    }
    div[data-testid="stMetric"] label {
        color: var(--text-muted) !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
        font-weight: 700 !important;
    }

    /* Tabs */
    button[data-baseweb="tab"] {
        color: var(--text-muted) !important;
        background: transparent !important;
        border-bottom: 2px solid transparent !important;
        font-weight: 500;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: var(--accent-light) !important;
        border-bottom-color: var(--accent) !important;
    }

    /* Cards */
    .job-card {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 12px;
        transition: all 0.2s ease;
    }
    .job-card:hover {
        border-color: var(--accent);
        transform: translateY(-1px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .job-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 4px;
    }
    .job-company {
        color: var(--accent-light);
        font-weight: 500;
        font-size: 0.9rem;
    }
    .job-meta {
        color: var(--text-muted);
        font-size: 0.8rem;
        margin-top: 6px;
    }
    .match-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .match-high { background: var(--green-bg); color: var(--green); border: 1px solid rgba(34,197,94,0.3); }
    .match-medium { background: var(--yellow-bg); color: var(--yellow); border: 1px solid rgba(234,179,8,0.3); }
    .match-low { background: var(--red-bg); color: var(--red); border: 1px solid rgba(239,68,68,0.3); }

    .status-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .status-new { background: var(--blue-bg); color: var(--blue); }
    .status-preparing { background: var(--yellow-bg); color: var(--yellow); }
    .status-applied { background: var(--green-bg); color: var(--green); }
    .status-interview { background: rgba(168,85,247,0.1); color: #a855f7; }
    .status-rejected { background: var(--red-bg); color: var(--red); }

    /* Pipeline */
    .pipeline-stage {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 14px;
        text-align: center;
        margin-bottom: 8px;
    }
    .pipeline-count {
        font-size: 1.8rem;
        font-weight: 800;
        color: var(--accent-light);
    }
    .pipeline-label {
        color: var(--text-muted);
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 4px;
    }

    /* Skill tags */
    .skill-tag {
        display: inline-block;
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        color: var(--text-secondary);
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 0.7rem;
        margin: 2px;
    }

    /* Buttons */
    .stButton > button {
        background: var(--accent) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 8px 16px !important;
        transition: all 0.2s ease !important;
    }
    .stButton > button:hover {
        background: var(--accent-light) !important;
        box-shadow: 0 0 20px var(--accent-glow) !important;
    }

    /* Input fields */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div {
        background: var(--bg-card) !important;
        border: 1px solid var(--border) !important;
        color: var(--text-primary) !important;
        border-radius: 8px !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 1px var(--accent) !important;
    }

    /* Headers */
    h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: var(--text-primary) !important;
        font-family: 'Inter', sans-serif !important;
    }

    /* Empty state */
    .empty-state {
        background: var(--bg-card);
        border: 1px dashed var(--border);
        border-radius: 12px;
        padding: 36px 20px;
        text-align: center;
        color: var(--text-muted);
        margin: 16px 0;
    }

    /* Pulse animation */
    @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.7; }
        50% { transform: scale(1.15); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.7; }
    }
    .pulsing-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        display: inline-block;
        animation: pulse 2s infinite ease-in-out;
    }

    /* Mobile Responsive Media Queries */
    @media (max-width: 768px) {
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
        div[data-testid="stMetric"] {
            margin-bottom: 8px !important;
            padding: 12px !important;
        }
        .pipeline-stage {
            padding: 10px !important;
        }
        .pipeline-count {
            font-size: 1.4rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# --- Resume Parsing & Matching Utilities ---
# ==============================================================================
KNOWN_TECH_SKILLS = [
    "python", "pytorch", "tensorflow", "keras", "langchain", "rag", "llms",
    "transformers", "nlp", "computer vision", "opencv", "scikit-learn",
    "pandas", "numpy", "sql", "postgresql", "fastapi", "flask", "docker",
    "kubernetes", "aws", "gcp", "azure", "mlops", "mlflow", "airflow",
    "git", "ci/cd", "bert", "spacy", "huggingface", "tableau", "spark",
    "kafka", "redis", "linux", "c++", "cuda", "onnx", "tensorrt", "react",
    "javascript", "typescript", "rest api", "graphql"
]

def extract_text_from_pdf(uploaded_file) -> str:
    """Extract raw text from an uploaded PDF file."""
    if not PYPDF_AVAILABLE:
        try:
            return uploaded_file.getvalue().decode("utf-8", errors="ignore")
        except Exception:
            return ""
    try:
        pdf_reader = pypdf.PdfReader(io.BytesIO(uploaded_file.getvalue()))
        text_parts = [page.extract_text() or "" for page in pdf_reader.pages]
        return "\n".join(text_parts)
    except Exception:
        return ""

def parse_resume_content(text: str) -> dict:
    """Analyze resume text to extract skills, contact hints, and generate a structured summary."""
    text_lower = text.lower()
    found_skills = []
    for skill in KNOWN_TECH_SKILLS:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text_lower):
            found_skills.append(skill.title() if len(skill) > 3 else skill.upper())

    # Extract email if present
    email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    extracted_email = email_match.group(0) if email_match else ""

    # Generate quick summary
    summary = f"Detected {len(found_skills)} relevant technical competencies. Strongest domains: " + ", ".join(found_skills[:6]) if found_skills else "General technical profile."

    return {
        "extracted_skills": found_skills,
        "extracted_email": extracted_email,
        "summary": summary,
        "raw_text_length": len(text)
    }

def calculate_match_score(job: dict, user_skills: list[str], target_roles: list[str], remote_pref: str) -> int:
    """Compute deterministic multi-factor match score based on current user profile."""
    user_skills_clean = {s.strip().lower() for s in user_skills if s.strip()}
    job_skills_clean = {s.strip().lower() for s in job.get("skills", [])}

    # 1. Skill overlap (60% weight)
    if job_skills_clean:
        overlap = len(user_skills_clean.intersection(job_skills_clean))
        skill_score = min(100, int((overlap / len(job_skills_clean)) * 100))
    else:
        skill_score = 75

    # 2. Role relevance (25% weight)
    role_score = 70
    job_title_lower = job.get("title", "").lower()
    for role in target_roles:
        if role.strip() and role.strip().lower() in job_title_lower:
            role_score = 95
            break

    # 3. Location/Remote preference (15% weight)
    loc_score = 80
    if remote_pref == "Any":
        loc_score = 90
    elif remote_pref.upper() == job.get("remote", "").upper():
        loc_score = 100
    elif remote_pref.upper() == "REMOTE" and job.get("remote", "") != "REMOTE":
        loc_score = 50

    total_score = int(0.60 * skill_score + 0.25 * role_score + 0.15 * loc_score)
    return max(45, min(99, total_score))


# ==============================================================================
# --- Session State Initialization ---
# ==============================================================================
def init_session_state():
    if "profile" not in st.session_state:
        st.session_state.profile = {
            "name": "Alex Rivera",
            "email": "alex.rivera.ai@example.com",
            "location": "San Francisco, CA",
            "linkedin": "linkedin.com/in/alex-rivera-ai",
            "github": "github.com/alexrivera-ai",
            "job_type": "Full-time",
            "remote_pref": "Hybrid",
            "min_salary": "120000",
            "target_roles": "ML Engineer, AI Engineer, Data Scientist",
            "skills": "Python\nPyTorch\nTensorFlow\nLangChain\nRAG\nLLMs\nFastAPI\nDocker\nKubernetes\nSQL\nMLOps",
            "experience": "AI & ML Engineer with 2+ years of experience building scalable LLM applications, RAG pipelines, and automated ML workflows.",
            "parsed_summary": "AI Engineer experienced in ML, LLMs, and Production Systems.",
            "resume_name": None,
        }

    if "jobs" not in st.session_state:
        st.session_state.jobs = [
            {"id": 1, "title": "Senior ML Engineer", "company": "Google", "location": "Mountain View, CA", "remote": "HYBRID", "salary": "$180K-$250K", "score": 94, "status": "HIGH_MATCH", "source": "LinkedIn", "skills": ["Python", "TensorFlow", "MLOps", "LLMs"], "posted": "2 days ago", "type": "FULL_TIME"},
            {"id": 2, "title": "AI Research Scientist", "company": "OpenAI", "location": "San Francisco, CA", "remote": "ONSITE", "salary": "$200K-$350K", "score": 91, "status": "HIGH_MATCH", "source": "Direct", "skills": ["PyTorch", "Transformers", "NLP", "Research"], "posted": "1 day ago", "type": "FULL_TIME"},
            {"id": 3, "title": "Data Scientist", "company": "Microsoft", "location": "Seattle, WA", "remote": "REMOTE", "salary": "$150K-$200K", "score": 87, "status": "ANALYZED", "source": "Indeed", "skills": ["Python", "SQL", "ML", "Azure"], "posted": "3 days ago", "type": "FULL_TIME"},
            {"id": 4, "title": "LLM Engineer", "company": "Anthropic", "location": "San Francisco, CA", "remote": "HYBRID", "salary": "$190K-$280K", "score": 88, "status": "HIGH_MATCH", "source": "LinkedIn", "skills": ["Python", "LangChain", "RAG", "LLMs"], "posted": "5 hours ago", "type": "FULL_TIME"},
            {"id": 5, "title": "Computer Vision Engineer", "company": "Tesla", "location": "Austin, TX", "remote": "ONSITE", "salary": "$160K-$220K", "score": 82, "status": "ANALYZED", "source": "LinkedIn", "skills": ["PyTorch", "OpenCV", "CNN", "YOLO"], "posted": "1 week ago", "type": "FULL_TIME"},
            {"id": 6, "title": "ML Platform Engineer", "company": "Meta", "location": "Menlo Park, CA", "remote": "HYBRID", "salary": "$170K-$240K", "score": 78, "status": "ANALYZED", "source": "Indeed", "skills": ["Python", "Kubernetes", "MLflow", "Airflow"], "posted": "4 days ago", "type": "FULL_TIME"},
            {"id": 7, "title": "NLP Engineer", "company": "Amazon", "location": "Seattle, WA", "remote": "REMOTE", "salary": "$145K-$195K", "score": 75, "status": "ANALYZED", "source": "Amazon Jobs", "skills": ["Python", "BERT", "SpaCy", "AWS"], "posted": "6 days ago", "type": "FULL_TIME"},
            {"id": 8, "title": "AI Software Engineer", "company": "Apple", "location": "Cupertino, CA", "remote": "ONSITE", "salary": "$175K-$250K", "score": 71, "status": "LOW_MATCH", "source": "LinkedIn", "skills": ["Swift", "Python", "CoreML", "ONNX"], "posted": "2 weeks ago", "type": "FULL_TIME"},
            {"id": 9, "title": "MLOps Engineer", "company": "Netflix", "location": "Los Gatos, CA", "remote": "REMOTE", "salary": "$165K-$230K", "score": 68, "status": "LOW_MATCH", "source": "Direct", "skills": ["Docker", "Kubernetes", "MLflow", "GCP"], "posted": "1 week ago", "type": "FULL_TIME"},
            {"id": 10, "title": "Deep Learning Engineer", "company": "Nvidia", "location": "Santa Clara, CA", "remote": "HYBRID", "salary": "$185K-$270K", "score": 65, "status": "LOW_MATCH", "source": "LinkedIn", "skills": ["CUDA", "PyTorch", "TensorRT", "C++"], "posted": "3 days ago", "type": "FULL_TIME"},
            {"id": 11, "title": "Data Analyst", "company": "Spotify", "location": "New York, NY", "remote": "HYBRID", "salary": "$95K-$130K", "score": 92, "status": "HIGH_MATCH", "source": "LinkedIn", "skills": ["Python", "SQL", "Tableau", "Pandas"], "posted": "1 day ago", "type": "FULL_TIME"},
            {"id": 12, "title": "GenAI Developer", "company": "StartupAI", "location": "Remote", "remote": "REMOTE", "salary": "$120K-$160K", "score": 88, "status": "ANALYZED", "source": "Wellfound", "skills": ["Python", "LangChain", "FastAPI", "RAG"], "posted": "12 hours ago", "type": "FULL_TIME"},
        ]

    if "applications" not in st.session_state:
        st.session_state.applications = [
            {
                "id": 1,
                "job_id": 1,
                "job_title": "Senior ML Engineer",
                "company": "Google",
                "location": "Mountain View, CA",
                "status": "APPLIED",
                "applied_date": "2026-09-10",
                "match_score": 94,
                "cover_letter": True,
                "cover_letter_text": "Dear Google Hiring Team,\n\nI am excited to apply for the Senior ML Engineer position. With extensive hands-on experience in TensorFlow, distributed training, and production MLOps pipelines, I have engineered reliable ML solutions serving high-throughput workloads.",
                "pitch": "Expertise in large-scale ML systems and production MLOps pipelines.",
            },
            {
                "id": 2,
                "job_id": 2,
                "job_title": "AI Research Scientist",
                "company": "OpenAI",
                "location": "San Francisco, CA",
                "status": "INTERVIEW",
                "applied_date": "2026-09-08",
                "match_score": 91,
                "cover_letter": True,
                "cover_letter_text": "Dear OpenAI Team,\n\nI am thrilled to submit my candidacy for the AI Research Scientist role. My background in transformer architectures, deep reinforcement learning, and cutting-edge NLP enables me to contribute meaningfully to foundational AI research.",
                "pitch": "Focused on frontier alignment and transformer optimizations.",
            },
            {
                "id": 3,
                "job_id": 3,
                "job_title": "Data Scientist",
                "company": "Microsoft",
                "location": "Seattle, WA",
                "status": "PENDING_APPROVAL",
                "applied_date": None,
                "match_score": 87,
                "cover_letter": True,
                "cover_letter_text": "Dear Microsoft Hiring Team,\n\nI am applying for the Data Scientist role in Azure AI. My deep background in predictive modeling, SQL data engineering, and machine learning aligns with Microsoft's customer-first AI vision.",
                "pitch": "Demonstrated track record of delivering end-to-end predictive models in enterprise cloud environments.",
            },
            {
                "id": 4,
                "job_id": 4,
                "job_title": "LLM Engineer",
                "company": "Anthropic",
                "location": "San Francisco, CA",
                "status": "PENDING_APPROVAL",
                "applied_date": None,
                "match_score": 88,
                "cover_letter": True,
                "cover_letter_text": "Dear Anthropic Team,\n\nI am writing to express my enthusiasm for the LLM Engineer position. Having built production RAG systems, evaluated reasoning workflows with LangChain, and fine-tuned models, I am eager to help build reliable, constitutional AI systems.",
                "pitch": "Hands-on experience developing autonomous AI agents and evaluation pipelines.",
            },
            {
                "id": 5,
                "job_id": 11,
                "job_title": "Data Analyst",
                "company": "Spotify",
                "location": "New York, NY",
                "status": "APPLIED",
                "applied_date": "2026-09-12",
                "match_score": 92,
                "cover_letter": True,
                "cover_letter_text": "Dear Spotify Team,\n\nI am excited to apply for the Data Analyst position. My expertise in SQL, Pandas, and interactive Tableau dashboards allows me to turn complex streaming insights into high-impact product decisions.",
                "pitch": "Experienced in large-scale behavioral data analytics and cohort metrics.",
            },
            {
                "id": 6,
                "job_id": 12,
                "job_title": "GenAI Developer",
                "company": "StartupAI",
                "location": "Remote",
                "status": "SAVED",
                "applied_date": None,
                "match_score": 88,
                "cover_letter": False,
                "cover_letter_text": "",
                "pitch": "",
            },
            {
                "id": 7,
                "job_id": 5,
                "job_title": "Computer Vision Engineer",
                "company": "Tesla",
                "location": "Austin, TX",
                "status": "REJECTED",
                "applied_date": "2026-09-01",
                "match_score": 82,
                "cover_letter": True,
                "cover_letter_text": "Dear Tesla Team,\n\nI am applying for the Computer Vision role with strong skills in PyTorch, YOLO, and real-time inference.",
                "pitch": "Real-time edge computer vision specialist.",
            },
        ]

    if "activities" not in st.session_state:
        st.session_state.activities = [
            ("🟢", "Job Discovered", "Senior ML Engineer at Google via LinkedIn", "2 hours ago"),
            ("🟢", "Job Discovered", "LLM Engineer at Anthropic via LinkedIn", "2 hours ago"),
            ("🟡", "AI Analysis Complete", "Data Scientist at Microsoft — 87% match", "1 hour ago"),
            ("🟡", "AI Analysis Complete", "LLM Engineer at Anthropic — 88% match", "1 hour ago"),
            ("🔵", "Application Prepared", "LLM Engineer at Anthropic — ready for review", "45 min ago"),
            ("🟣", "Interview Scheduled", "AI Research Scientist at OpenAI — Sep 18", "1 day ago"),
            ("🟢", "Application Submitted", "Data Analyst at Spotify — applied via portal", "1 day ago"),
            ("🔴", "Status Updated", "Computer Vision Engineer at Tesla — Archived", "3 days ago"),
        ]

    if "automation_settings" not in st.session_state:
        st.session_state.automation_settings = {
            "auto_discover": True,
            "auto_analyze": True,
            "auto_prepare": False,
            "is_active": True,
            "last_discovery": "2 hours ago",
            "last_analysis": "1 hour ago",
            "last_prep": "45 minutes ago",
        }

    if "editing_app_id" not in st.session_state:
        st.session_state.editing_app_id = None

init_session_state()


def recalculate_all_job_scores():
    """Recalculate match scores across all jobs based on active profile settings."""
    profile = st.session_state.profile
    skills_list = profile["skills"].splitlines()
    target_roles = [r.strip() for r in profile["target_roles"].split(",") if r.strip()]
    remote_pref = profile["remote_pref"]

    for job in st.session_state.jobs:
        new_score = calculate_match_score(job, skills_list, target_roles, remote_pref)
        job["score"] = new_score
        if new_score >= 90:
            job["status"] = "HIGH_MATCH"
        elif new_score >= 75:
            job["status"] = "ANALYZED"
        else:
            job["status"] = "LOW_MATCH"


# ==============================================================================
# --- Sidebar ---
# ==============================================================================
with st.sidebar:
    st.markdown("## 🤖 AI Job Agent")
    st.markdown("---")

    st.markdown("### ⚡ Quick Actions")

    if st.button("🔍 Run Job Discovery", use_container_width=True, key="side_run_discovery"):
        with st.spinner("Polling job sources (LinkedIn, Indeed, RemoteOK)..."):
            new_id = max([j["id"] for j in st.session_state.jobs], default=10) + 1
            sample_new_jobs = [
                {"id": new_id, "title": "AI Platform Engineer", "company": "Cohere", "location": "Remote", "remote": "REMOTE", "salary": "$170K-$230K", "source": "LinkedIn RSS", "skills": ["Python", "FastAPI", "Docker", "LLMs"], "posted": "Just now", "type": "FULL_TIME"},
                {"id": new_id + 1, "title": "ML Infrastructure Specialist", "company": "Hugging Face", "location": "Remote", "remote": "REMOTE", "salary": "$160K-$210K", "source": "Direct Feed", "skills": ["Python", "PyTorch", "Transformers", "Kubernetes"], "posted": "Just now", "type": "FULL_TIME"},
            ]
            skills_list = st.session_state.profile["skills"].splitlines()
            target_roles = [r.strip() for r in st.session_state.profile["target_roles"].split(",") if r.strip()]
            for nj in sample_new_jobs:
                nj["score"] = calculate_match_score(nj, skills_list, target_roles, st.session_state.profile["remote_pref"])
                nj["status"] = "HIGH_MATCH" if nj["score"] >= 90 else "ANALYZED"
                st.session_state.jobs.insert(0, nj)

            st.session_state.automation_settings["last_discovery"] = "Just now"
            st.session_state.activities.insert(0, ("🟢", "Job Discovered", f"{sample_new_jobs[0]['title']} at {sample_new_jobs[0]['company']}", "Just now"))
            st.toast(f"Discovery complete: Found {len(sample_new_jobs)} new opportunities!", icon="🔍")
            st.rerun()

    if st.button("📊 Analyze Pending Jobs", use_container_width=True, key="side_analyze_jobs"):
        with st.spinner("Recalculating AI match scores & compatibility..."):
            recalculate_all_job_scores()
            st.session_state.automation_settings["last_analysis"] = "Just now"
            st.session_state.activities.insert(0, ("🟡", "AI Analysis Complete", f"Batch analyzed {len(st.session_state.jobs)} jobs against active profile", "Just now"))
            st.toast("AI analysis complete for all jobs!", icon="📊")
            st.rerun()

    if st.button("🚀 Prepare Applications", use_container_width=True, key="side_prep_apps"):
        with st.spinner("Generating tailored cover letters and application materials..."):
            prep_count = 0
            for job in st.session_state.jobs:
                if job["score"] >= 85:
                    existing = any(a["job_id"] == job["id"] for a in st.session_state.applications)
                    if not existing:
                        new_app_id = max([a["id"] for a in st.session_state.applications], default=0) + 1
                        st.session_state.applications.insert(0, {
                            "id": new_app_id,
                            "job_id": job["id"],
                            "job_title": job["title"],
                            "company": job["company"],
                            "location": job["location"],
                            "status": "PENDING_APPROVAL",
                            "applied_date": None,
                            "match_score": job["score"],
                            "cover_letter": True,
                            "cover_letter_text": f"Dear {job['company']} Hiring Team,\n\nI am writing to express my strong interest in the {job['title']} position. With a deep foundation in {', '.join(job['skills'][:3])} and hands-on experience solving real-world engineering challenges, I am confident in my ability to make an immediate positive impact on your team.",
                            "pitch": f"Tailored for {job['title']} with focus on {', '.join(job['skills'][:2])}.",
                        })
                        prep_count += 1
            st.session_state.automation_settings["last_prep"] = "Just now"
            st.session_state.activities.insert(0, ("🔵", "Batch Applications Prepared", f"Prepared {prep_count} high-match applications for review", "Just now"))
            st.toast(f"Prepared {prep_count} new applications for review!", icon="🚀")
            st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ Automation Settings")
    st.session_state.automation_settings["auto_discover"] = st.toggle(
        "Auto-discover jobs",
        value=st.session_state.automation_settings["auto_discover"],
        key="toggle_auto_discover"
    )
    st.session_state.automation_settings["auto_analyze"] = st.toggle(
        "AI job analysis",
        value=st.session_state.automation_settings["auto_analyze"],
        key="toggle_auto_analyze"
    )
    st.session_state.automation_settings["auto_prepare"] = st.toggle(
        "Auto-prepare applications",
        value=st.session_state.automation_settings["auto_prepare"],
        key="toggle_auto_prepare"
    )
    st.caption("🔒 Human approval required before submission")

    st.markdown("---")
    st.markdown("### 🔗 Job Sources")
    sources = {
        "LinkedIn RSS": True,
        "Indeed API": True,
        "Wellfound": True,
        "Direct RSS Feed": True,
    }
    for name, active in sources.items():
        status_dot = "🟢" if active else "🔴"
        st.markdown(f"{status_dot} **{name}**")

    st.markdown("---")
    st.markdown("### 📊 Active Summary")
    high_match_count = sum(1 for j in st.session_state.jobs if j["score"] >= 90)
    pending_app_count = sum(1 for a in st.session_state.applications if a["status"] == "PENDING_APPROVAL")
    applied_count = sum(1 for a in st.session_state.applications if a["status"] == "APPLIED")
    st.markdown(f"""
    - **{len(st.session_state.jobs)}** active jobs tracked
    - **{high_match_count}** high matches (≥90%)
    - **{pending_app_count}** awaiting your review
    - **{applied_count}** submitted applications
    """)


# ==============================================================================
# --- Main Header & Live KPI Metrics ---
# ==============================================================================
st.markdown("# 🤖 AI Job Application Automation Agent")
st.markdown("*Autonomous job discovery, intelligent AI matching, and human-supervised application preparation.*")

total_jobs = len(st.session_state.jobs)
high_matches = sum(1 for j in st.session_state.jobs if j["score"] >= 90)
prepared_apps = sum(1 for a in st.session_state.applications if a["status"] in ["PENDING_APPROVAL", "PREPARING"])
applied_apps = sum(1 for a in st.session_state.applications if a["status"] == "APPLIED")
interview_apps = sum(1 for a in st.session_state.applications if a["status"] == "INTERVIEW")
avg_match = int(sum(j["score"] for j in st.session_state.jobs) / max(1, total_jobs))

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("📋 Jobs Tracked", f"{total_jobs}", f"+{total_jobs - 10} new")
col2.metric("🎯 High Matches", f"{high_matches}", f"{int(high_matches/max(1, total_jobs)*100)}% of total")
col3.metric("📝 In Review", f"{prepared_apps}", "Pending approval")
col4.metric("✅ Applied", f"{applied_apps}", "Active submissions")
col5.metric("🎤 Interviews", f"{interview_apps}", "Upcoming rounds")
col6.metric("📈 Avg Match", f"{avg_match}%", "Compatibility")

st.markdown("---")


# ==============================================================================
# --- Tabs Navigation ---
# ==============================================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Job Board",
    "📊 Application Pipeline",
    "⚙️ Automation",
    "📈 Analytics",
    "👤 Profile & Resume"
])


# ==============================================================================
# --- TAB 1: JOB BOARD ---
# ==============================================================================
with tab1:
    col_search, col_filter = st.columns([3, 1])
    with col_search:
        search = st.text_input(
            "Search jobs",
            placeholder="Search by job title, company, or technical skill (e.g. Python, LLMs, Google)...",
            label_visibility="collapsed",
            key="job_board_search"
        )
    with col_filter:
        remote_filter = st.selectbox(
            "Remote Filter",
            ["All", "Remote", "Hybrid", "Onsite"],
            label_visibility="collapsed",
            key="job_board_remote_filter"
        )

    filtered_jobs = st.session_state.jobs
    if search:
        q = search.lower().strip()
        filtered_jobs = [
            j for j in filtered_jobs
            if q in j["title"].lower() or q in j["company"].lower() or any(q in s.lower() for s in j["skills"])
        ]
    if remote_filter != "All":
        filtered_jobs = [j for j in filtered_jobs if j["remote"] == remote_filter.upper()]

    st.markdown(f"**Showing {len(filtered_jobs)} matching opportunities**")

    if not filtered_jobs:
        st.markdown("""
        <div class="empty-state">
            <div style="font-size: 2rem; margin-bottom: 8px;">🔍</div>
            <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">No matching jobs found</div>
            <div>Try adjusting your search query or switching remote filter options.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        for job in filtered_jobs:
            score_class = "match-high" if job["score"] >= 90 else ("match-medium" if job["score"] >= 75 else "match-low")
            status_class = {
                "HIGH_MATCH": "status-applied",
                "ANALYZED": "status-preparing",
                "LOW_MATCH": "status-rejected",
            }.get(job["status"], "status-new")

            skills_html = "".join([f'<span class="skill-tag">{s}</span>' for s in job["skills"]])

            existing_app = next((a for a in st.session_state.applications if a["job_id"] == job["id"]), None)
            app_status_indicator = ""
            if existing_app:
                app_status_indicator = f'<span class="status-badge status-applied" style="margin-right: 6px;">Pipeline: {existing_app["status"].replace("_", " ")}</span>'

            st.markdown(f"""
            <div class="job-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <div class="job-title">{job['title']}</div>
                        <div class="job-company">{job['company']} · <span style="color: var(--text-muted);">{job.get('source', 'Web')}</span></div>
                        <div class="job-meta">📍 {job['location']} · 🏠 {job['remote']} · 💰 {job['salary']} · 📅 {job['posted']}</div>
                        <div style="margin-top: 8px;">{skills_html}</div>
                    </div>
                    <div style="text-align: right;">
                        <span class="match-badge {score_class}">{job['score']}% match</span>
                        <div style="margin-top: 8px;">
                            {app_status_indicator}
                            <span class="status-badge {status_class}">{job['status'].replace('_', ' ').title()}</span>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_a, col_b, col_c = st.columns([1.2, 1.2, 3.6])
            with col_a:
                prep_label = "📝 Prepared" if existing_app else "📝 Prepare"
                if st.button(prep_label, key=f"prep_job_{job['id']}", use_container_width=True):
                    if existing_app:
                        st.toast(f"Application for {job['title']} is already in Pipeline ({existing_app['status']})!", icon="ℹ️")
                    else:
                        new_id = max([a["id"] for a in st.session_state.applications], default=0) + 1
                        st.session_state.applications.insert(0, {
                            "id": new_id,
                            "job_id": job["id"],
                            "job_title": job["title"],
                            "company": job["company"],
                            "location": job["location"],
                            "status": "PENDING_APPROVAL",
                            "applied_date": None,
                            "match_score": job["score"],
                            "cover_letter": True,
                            "cover_letter_text": f"Dear {job['company']} Hiring Team,\n\nI am thrilled to submit my application for the {job['title']} role. With strong skills in {', '.join(job['skills'][:3])} and dedicated experience building scalable AI solutions, I look forward to contributing to your innovative projects.\n\nSincerely,\n{st.session_state.profile['name']}",
                            "pitch": f"Specialized in {', '.join(job['skills'][:3])}.",
                        })
                        st.session_state.activities.insert(0, ("🔵", "Application Prepared", f"{job['title']} at {job['company']} ready for review", "Just now"))
                        st.toast(f"✅ Prepared application for {job['title']}! Review it in Application Pipeline.", icon="📝")
                        st.rerun()

            with col_b:
                if st.button("🔍 Analyze", key=f"analyze_job_{job['id']}", use_container_width=True):
                    skills_list = st.session_state.profile["skills"].splitlines()
                    target_roles = [r.strip() for r in st.session_state.profile["target_roles"].split(",") if r.strip()]
                    job["score"] = calculate_match_score(job, skills_list, target_roles, st.session_state.profile["remote_pref"])
                    job["status"] = "HIGH_MATCH" if job["score"] >= 90 else ("ANALYZED" if job["score"] >= 75 else "LOW_MATCH")
                    st.toast(f"Analyzed {job['title']} at {job['company']}: {job['score']}% match score computed!", icon="🔍")
                    st.rerun()


# ==============================================================================
# --- TAB 2: APPLICATION PIPELINE ---
# ==============================================================================
with tab2:
    st.markdown("### 📊 Application Pipeline")

    saved_count = sum(1 for a in st.session_state.applications if a["status"] == "SAVED")
    prep_count = sum(1 for a in st.session_state.applications if a["status"] == "PREPARING")
    review_count = sum(1 for a in st.session_state.applications if a["status"] == "PENDING_APPROVAL")
    applied_count = sum(1 for a in st.session_state.applications if a["status"] == "APPLIED")
    interview_count = sum(1 for a in st.session_state.applications if a["status"] == "INTERVIEW")
    rejected_count = sum(1 for a in st.session_state.applications if a["status"] == "REJECTED")

    pipeline_cols = st.columns(6)
    stages = [
        ("💾 Saved", saved_count, "var(--blue)"),
        ("⏳ Preparing", prep_count, "var(--yellow)"),
        ("👁️ Review", review_count, "var(--orange)"),
        ("✅ Applied", applied_count, "var(--green)"),
        ("🎤 Interview", interview_count, "#a855f7"),
        ("❌ Archived", rejected_count, "var(--red)"),
    ]
    for col, (label, count, color) in zip(pipeline_cols, stages):
        with col:
            st.markdown(f"""
            <div class="pipeline-stage">
                <div class="pipeline-count" style="color: {color};">{count}</div>
                <div class="pipeline-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📋 Application Records")

    app_filter = st.selectbox(
        "Filter applications by status",
        ["All", "Pending Approval", "Applied", "Interview", "Saved", "Rejected"],
        key="app_filter_select"
    )

    filtered_apps = st.session_state.applications
    if app_filter != "All":
        target_status = app_filter.replace(" ", "_").upper()
        filtered_apps = [a for a in filtered_apps if a["status"] == target_status]

    if not filtered_apps:
        st.markdown(f"""
        <div class="empty-state">
            <div style="font-size: 2rem; margin-bottom: 8px;">📂</div>
            <div style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">No applications in this category</div>
            <div>Select 'All' or prepare new job applications from the Job Board.</div>
        </div>
        """, unsafe_allow_html=True)

    for app in filtered_apps:
        status_map = {
            "APPLIED": ("status-applied", "✅ Applied"),
            "INTERVIEW": ("status-interview", "🎤 Interview"),
            "PENDING_APPROVAL": ("status-preparing", "👁️ Pending Review"),
            "PREPARING": ("status-new", "⏳ Preparing"),
            "SAVED": ("status-new", "💾 Saved"),
            "REJECTED": ("status-rejected", "❌ Archived"),
        }
        status_class, status_label = status_map.get(app["status"], ("status-new", app["status"]))
        score_class = "match-high" if app.get("match_score", 80) >= 90 else ("match-medium" if app.get("match_score", 80) >= 75 else "match-low")

        st.markdown(f"""
        <div class="job-card">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                <div>
                    <div class="job-title">{app['job_title']}</div>
                    <div class="job-company">{app['company']} · <span style="color: var(--text-muted); font-size: 0.8rem;">{app.get('location', '')}</span></div>
                    <div class="job-meta">
                        {'📅 Applied: ' + app['applied_date'] if app.get('applied_date') else '⏳ Awaiting submission'} · 
                        {'📝 Cover Letter Ready' if app.get('cover_letter') else '📄 No Cover Letter'}
                    </div>
                </div>
                <div style="text-align: right;">
                    <span class="match-badge {score_class}">{app.get('match_score', 85)}% match</span>
                    <div style="margin-top: 6px;">
                        <span class="status-badge {status_class}">{status_label}</span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 2.4])

        if app["status"] == "PENDING_APPROVAL":
            with c1:
                if st.button("✅ Approve & Submit", key=f"app_approve_{app['id']}", use_container_width=True):
                    app["status"] = "APPLIED"
                    app["applied_date"] = datetime.now().strftime("%Y-%m-%d")
                    st.session_state.activities.insert(0, ("🟢", "Application Submitted", f"{app['job_title']} at {app['company']} submitted via portal", "Just now"))
                    st.toast(f"Application for {app['job_title']} at {app['company']} approved & marked as Applied!", icon="✅")
                    st.rerun()

        with c2:
            edit_toggle_label = "🔼 Close Review" if st.session_state.editing_app_id == app["id"] else "✏️ View / Edit"
            if st.button(edit_toggle_label, key=f"app_edit_btn_{app['id']}", use_container_width=True):
                if st.session_state.editing_app_id == app["id"]:
                    st.session_state.editing_app_id = None
                else:
                    st.session_state.editing_app_id = app["id"]
                st.rerun()

        with c3:
            if app["status"] not in ["REJECTED", "ARCHIVED"]:
                if st.button("❌ Archive", key=f"app_archive_{app['id']}", use_container_width=True):
                    app["status"] = "REJECTED"
                    st.toast(f"Application {app['job_title']} moved to Archive.", icon="ℹ️")
                    st.rerun()

        if st.session_state.editing_app_id == app["id"]:
            with st.expander(f"📝 Review Application Materials: {app['job_title']} @ {app['company']}", expanded=True):
                col_e1, col_e2 = st.columns([1, 1])
                with col_e1:
                    st.markdown("**Custom Pitch:**")
                    new_pitch = st.text_input("Pitch Summary", value=app.get("pitch", ""), key=f"pitch_input_{app['id']}")
                    st.markdown("**Status:**")
                    new_app_status = st.selectbox(
                        "Update Status",
                        ["PENDING_APPROVAL", "APPLIED", "INTERVIEW", "SAVED", "REJECTED"],
                        index=["PENDING_APPROVAL", "APPLIED", "INTERVIEW", "SAVED", "REJECTED"].index(app["status"]),
                        key=f"status_select_{app['id']}"
                    )
                with col_e2:
                    st.markdown("**Tailored Cover Letter:**")
                    new_cl = st.text_area("Cover Letter Text", value=app.get("cover_letter_text", ""), height=160, key=f"cl_input_{app['id']}")

                if st.button("💾 Save Materials", key=f"save_mat_{app['id']}", use_container_width=True):
                    app["pitch"] = new_pitch
                    app["cover_letter_text"] = new_cl
                    app["status"] = new_app_status
                    if new_app_status == "APPLIED" and not app.get("applied_date"):
                        app["applied_date"] = datetime.now().strftime("%Y-%m-%d")
                    st.session_state.editing_app_id = None
                    st.toast(f"Saved application details for {app['job_title']}!", icon="✅")
                    st.rerun()


# ==============================================================================
# --- TAB 3: AUTOMATION CONTROL CENTER ---
# ==============================================================================
with tab3:
    st.markdown("### ⚙️ Automation Control Center")

    col_status, col_controls = st.columns([2, 1])

    with col_status:
        auto_on = st.session_state.automation_settings["auto_discover"] or st.session_state.automation_settings["auto_analyze"]
        status_color = "#22c55e" if auto_on else "#eab308"
        status_text = "Automation Active & Monitoring" if auto_on else "Automation Idle (Manual Mode)"

        st.markdown(f"""
        <div class="job-card">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                <div class="pulsing-dot" style="background: {status_color};"></div>
                <span style="color: var(--text-primary); font-weight: 600; font-size: 1.1rem;">{status_text}</span>
            </div>
            <div style="color: var(--text-secondary); font-size: 0.9rem; line-height: 1.8;">
                <p>✅ Last discovery run: <strong>{st.session_state.automation_settings['last_discovery']}</strong> — active source polling</p>
                <p>✅ Last analysis batch: <strong>{st.session_state.automation_settings['last_analysis']}</strong> — matched against current profile</p>
                <p>✅ Last application prep: <strong>{st.session_state.automation_settings['last_prep']}</strong></p>
                <p>⏳ Scheduled interval: <strong>Every 10 minutes</strong> (Compliant background workers)</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_controls:
        st.markdown("#### 🎛️ Manual Batch Controls")
        if st.button("🔄 Run Discovery Now", use_container_width=True, key="tab3_run_disc"):
            new_id = max([j["id"] for j in st.session_state.jobs], default=10) + 1
            added_job = {"id": new_id, "title": "GenAI Systems Engineer", "company": "Scale AI", "location": "San Francisco, CA", "remote": "HYBRID", "salary": "$175K-$245K", "source": "Wellfound", "skills": ["Python", "PyTorch", "LLMs", "RAG"], "posted": "Just now", "type": "FULL_TIME"}
            skills_list = st.session_state.profile["skills"].splitlines()
            target_roles = [r.strip() for r in st.session_state.profile["target_roles"].split(",") if r.strip()]
            added_job["score"] = calculate_match_score(added_job, skills_list, target_roles, st.session_state.profile["remote_pref"])
            added_job["status"] = "HIGH_MATCH"
            st.session_state.jobs.insert(0, added_job)
            st.session_state.automation_settings["last_discovery"] = "Just now"
            st.session_state.activities.insert(0, ("🟢", "Job Discovered", "GenAI Systems Engineer at Scale AI", "Just now"))
            st.toast("Discovered new live job from Wellfound!", icon="🔄")
            st.rerun()

        if st.button("🧠 Analyze All Pending", use_container_width=True, key="tab3_run_ana"):
            recalculate_all_job_scores()
            st.session_state.automation_settings["last_analysis"] = "Just now"
            st.toast("AI analysis completed across all active jobs!", icon="🧠")
            st.rerun()

        if st.button("📧 Prepare High Matches (≥85%)", use_container_width=True, key="tab3_run_prep"):
            count = 0
            for job in st.session_state.jobs:
                if job["score"] >= 85 and not any(a["job_id"] == job["id"] for a in st.session_state.applications):
                    new_app_id = max([a["id"] for a in st.session_state.applications], default=0) + 1
                    st.session_state.applications.insert(0, {
                        "id": new_app_id,
                        "job_id": job["id"],
                        "job_title": job["title"],
                        "company": job["company"],
                        "location": job["location"],
                        "status": "PENDING_APPROVAL",
                        "applied_date": None,
                        "match_score": job["score"],
                        "cover_letter": True,
                        "cover_letter_text": f"Dear {job['company']} Hiring Team,\n\nI am excited to apply for the {job['title']} role. With direct experience in {', '.join(job['skills'][:3])}, I look forward to contributing to your team's mission.",
                        "pitch": f"Focused on {', '.join(job['skills'][:2])}.",
                    })
                    count += 1
            st.toast(f"Prepared {count} new tailored applications!", icon="📧")
            st.rerun()

    st.markdown("---")
    st.markdown("### 📜 Real-Time Activity Log")

    for icon, event_type, detail, time_label in st.session_state.activities:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border);">
            <span style="font-size: 1.2rem;">{icon}</span>
            <div style="flex: 1;">
                <span style="color: var(--text-primary); font-weight: 500;">{event_type}</span>
                <span style="color: var(--text-muted);"> — {detail}</span>
            </div>
            <span style="color: var(--text-muted); font-size: 0.8rem;">{time_label}</span>
        </div>
        """, unsafe_allow_html=True)


# ==============================================================================
# --- TAB 4: ANALYTICS ---
# ==============================================================================
with tab4:
    st.markdown("### 📈 Analytics Dashboard")

    if not PLOTLY_AVAILABLE:
        st.info("Plotly charts available when deployed with standard graphical environment.")
    else:
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.markdown("#### Match Score Distribution")
            score_90 = sum(1 for j in st.session_state.jobs if j["score"] >= 90)
            score_75 = sum(1 for j in st.session_state.jobs if 75 <= j["score"] < 90)
            score_50 = sum(1 for j in st.session_state.jobs if 50 <= j["score"] < 75)
            score_low = sum(1 for j in st.session_state.jobs if j["score"] < 50)

            fig_dist = px.bar(
                x=["90-100% (High)", "75-89% (Good)", "50-74% (Fair)", "<50% (Low)"],
                y=[score_90, score_75, score_50, score_low],
                color=["#22c55e", "#6366f1", "#eab308", "#ef4444"],
                color_discrete_map="identity",
                template="plotly_dark",
            )
            fig_dist.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8"),
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(42,42,58,0.5)"),
                showlegend=False,
                height=300,
                margin=dict(t=10, b=10, l=10, r=10),
            )
            st.plotly_chart(fig_dist, use_container_width=True)

        with col_chart2:
            st.markdown("#### Application Funnel")
            f_disc = len(st.session_state.jobs)
            f_match = sum(1 for j in st.session_state.jobs if j["score"] >= 80)
            f_prep = len(st.session_state.applications)
            f_appl = sum(1 for a in st.session_state.applications if a["status"] in ["APPLIED", "INTERVIEW"])
            f_intr = sum(1 for a in st.session_state.applications if a["status"] == "INTERVIEW")

            fig_funnel = go.Figure(go.Funnel(
                y=["Discovered", "High Matches", "Prepared", "Submitted", "Interviews"],
                x=[f_disc, f_match, f_prep, f_appl, f_intr],
                marker=dict(color=["#3b82f6", "#6366f1", "#eab308", "#22c55e", "#a855f7"]),
                textinfo="value+percent initial",
            ))
            fig_funnel.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8"),
                height=300,
                margin=dict(t=10, b=10, l=10, r=10),
            )
            st.plotly_chart(fig_funnel, use_container_width=True)

        col_chart3, col_chart4 = st.columns(2)

        with col_chart3:
            st.markdown("#### Opportunities by Remote Category")
            remote_counts = {}
            for j in st.session_state.jobs:
                r = j.get("remote", "OTHER")
                remote_counts[r] = remote_counts.get(r, 0) + 1

            fig_source = px.pie(
                names=list(remote_counts.keys()),
                values=list(remote_counts.values()),
                template="plotly_dark",
                hole=0.4,
                color_discrete_sequence=["#6366f1", "#22c55e", "#3b82f6", "#eab308"]
            )
            fig_source.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8"),
                height=300,
                margin=dict(t=10, b=10, l=10, r=10),
                showlegend=True,
                legend=dict(font=dict(size=10)),
            )
            st.plotly_chart(fig_source, use_container_width=True)

        with col_chart4:
            st.markdown("#### Weekly Application Pace")
            fig_week = px.line(
                x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                y=[4, 7, 5, 11, 8, 3, applied_apps],
                template="plotly_dark",
                markers=True,
            )
            fig_week.update_traces(line=dict(color="#6366f1", width=3), marker=dict(size=8, color="#818cf8"))
            fig_week.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8"),
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(42,42,58,0.5)"),
                height=300,
                margin=dict(t=10, b=10, l=10, r=10),
            )
            st.plotly_chart(fig_week, use_container_width=True)


# ==============================================================================
# --- TAB 5: PROFILE & REAL RESUME PARSING ---
# ==============================================================================
with tab5:
    st.markdown("### 👤 Candidate Profile & Resume Parser")

    col_profile, col_resume = st.columns([1, 1])

    with col_profile:
        st.markdown("#### Personal Info")
        name_input = st.text_input("Full Name", value=st.session_state.profile["name"], key="prof_name_input")
        email_input = st.text_input("Email Address", value=st.session_state.profile["email"], key="prof_email_input")
        location_input = st.text_input("Location", value=st.session_state.profile["location"], key="prof_loc_input")
        linkedin_input = st.text_input("LinkedIn Profile URL", value=st.session_state.profile["linkedin"], key="prof_li_input")
        github_input = st.text_input("GitHub Portfolio URL", value=st.session_state.profile["github"], key="prof_gh_input")

        st.markdown("#### Target Preferences")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            job_types = ["Full-time", "Contract", "Part-time"]
            cur_jt_idx = job_types.index(st.session_state.profile["job_type"]) if st.session_state.profile["job_type"] in job_types else 0
            job_type_input = st.selectbox("Job Type", job_types, index=cur_jt_idx, key="prof_jt_input")

            remote_types = ["Remote", "Hybrid", "Onsite", "Any"]
            cur_rt_idx = remote_types.index(st.session_state.profile["remote_pref"]) if st.session_state.profile["remote_pref"] in remote_types else 1
            remote_pref_input = st.selectbox("Remote Preference", remote_types, index=cur_rt_idx, key="prof_rt_input")

        with col_t2:
            salary_input = st.text_input("Min Salary (USD)", value=st.session_state.profile["min_salary"], key="prof_sal_input")
            roles_input = st.text_input("Target Roles (comma-separated)", value=st.session_state.profile["target_roles"], key="prof_roles_input")

    with col_resume:
        st.markdown("#### 📄 Resume Upload & Extraction")
        uploaded = st.file_uploader(
            "Upload your resume (PDF or TXT) to auto-extract skills",
            type=["pdf", "txt"],
            key="resume_uploader_widget"
        )

        if uploaded:
            extracted_text = extract_text_from_pdf(uploaded)
            if extracted_text:
                parsed_data = parse_resume_content(extracted_text)
                st.session_state.profile["resume_name"] = uploaded.name
                st.session_state.profile["parsed_summary"] = parsed_data["summary"]

                # Auto-append extracted skills if new
                current_skills_set = set(st.session_state.profile["skills"].splitlines())
                for es in parsed_data["extracted_skills"]:
                    current_skills_set.add(es)
                st.session_state.profile["skills"] = "\n".join(sorted(current_skills_set))

                st.success(f"✅ Successfully parsed '{uploaded.name}' ({parsed_data['raw_text_length']} chars extracted)")
                st.markdown(f"**Extracted Summary:** {parsed_data['summary']}")
                st.markdown(f"**Identified Competencies:** {', '.join(parsed_data['extracted_skills'][:10])}")
            else:
                st.info(f"Uploaded {uploaded.name}. Enter skills below to customize.")

        st.markdown("#### Technical Skills")
        skills_input = st.text_area(
            "Your Skills (one per line — matches directly against job requirements)",
            value=st.session_state.profile["skills"],
            height=180,
            key="prof_skills_textarea"
        )

        st.markdown("#### Work Experience Summary")
        exp_input = st.text_area(
            "Experience Highlights",
            value=st.session_state.profile["experience"],
            height=120,
            key="prof_exp_textarea"
        )

    if st.button("💾 Save Profile & Recalculate Job Matching", use_container_width=True, key="save_profile_btn"):
        st.session_state.profile["name"] = name_input
        st.session_state.profile["email"] = email_input
        st.session_state.profile["location"] = location_input
        st.session_state.profile["linkedin"] = linkedin_input
        st.session_state.profile["github"] = github_input
        st.session_state.profile["job_type"] = job_type_input
        st.session_state.profile["remote_pref"] = remote_pref_input
        st.session_state.profile["min_salary"] = salary_input
        st.session_state.profile["target_roles"] = roles_input
        st.session_state.profile["skills"] = skills_input
        st.session_state.profile["experience"] = exp_input

        recalculate_all_job_scores()
        st.session_state.activities.insert(0, ("💾", "Profile Updated", "Profile saved and job matching scores recalculated", "Just now"))
        st.toast("Profile updated! All job matching scores have been recalculated.", icon="✅")
        st.rerun()
