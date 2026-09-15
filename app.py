import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random

# --- Page Config ---
st.set_page_config(
    page_title="AI Job Application Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Premium Dark Theme CSS ---
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
        padding-top: 2rem;
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

    /* Metrics */
    div[data-testid="stMetric"] {
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 20px;
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
        padding: 20px;
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
        padding: 16px;
        text-align: center;
    }
    .pipeline-count {
        font-size: 2rem;
        font-weight: 800;
        color: var(--accent-light);
    }
    .pipeline-label {
        color: var(--text-muted);
        font-size: 0.8rem;
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
        padding: 8px 20px !important;
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

    /* Dividers */
    hr { border-color: var(--border) !important; }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg-secondary); }
    ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

    /* Tables */
    .stDataFrame { border-radius: 12px !important; overflow: hidden; }
</style>
""", unsafe_allow_html=True)


# --- Demo Data ---
@st.cache_data
def get_demo_jobs():
    jobs = [
        {"id": 1, "title": "Senior ML Engineer", "company": "Google", "location": "Mountain View, CA", "remote": "HYBRID", "salary": "$180K-$250K", "score": 94, "status": "HIGH_MATCH", "source": "LinkedIn", "skills": ["Python", "TensorFlow", "MLOps", "LLMs"], "posted": "2 days ago", "type": "FULL_TIME"},
        {"id": 2, "title": "AI Research Scientist", "company": "OpenAI", "location": "San Francisco, CA", "remote": "ONSITE", "salary": "$200K-$350K", "score": 91, "status": "HIGH_MATCH", "source": "Direct", "skills": ["PyTorch", "Transformers", "NLP", "Research"], "posted": "1 day ago", "type": "FULL_TIME"},
        {"id": 3, "title": "Data Scientist", "company": "Microsoft", "location": "Seattle, WA", "remote": "REMOTE", "salary": "$150K-$200K", "score": 87, "status": "ANALYZED", "source": "Indeed", "skills": ["Python", "SQL", "ML", "Azure"], "posted": "3 days ago", "type": "FULL_TIME"},
        {"id": 4, "title": "LLM Engineer", "company": "Anthropic", "location": "San Francisco, CA", "remote": "HYBRID", "salary": "$190K-$280K", "score": 85, "status": "ANALYZED", "source": "LinkedIn", "skills": ["Python", "LangChain", "RAG", "LLMs"], "posted": "5 hours ago", "type": "FULL_TIME"},
        {"id": 5, "title": "Computer Vision Engineer", "company": "Tesla", "location": "Austin, TX", "remote": "ONSITE", "salary": "$160K-$220K", "score": 82, "status": "ANALYZED", "source": "LinkedIn", "skills": ["PyTorch", "OpenCV", "CNN", "YOLO"], "posted": "1 week ago", "type": "FULL_TIME"},
        {"id": 6, "title": "ML Platform Engineer", "company": "Meta", "location": "Menlo Park, CA", "remote": "HYBRID", "salary": "$170K-$240K", "score": 78, "status": "ANALYZED", "source": "Indeed", "skills": ["Python", "Kubernetes", "MLflow", "Airflow"], "posted": "4 days ago", "type": "FULL_TIME"},
        {"id": 7, "title": "NLP Engineer", "company": "Amazon", "location": "Seattle, WA", "remote": "REMOTE", "salary": "$145K-$195K", "score": 75, "status": "ANALYZED", "source": "Amazon Jobs", "skills": ["Python", "BERT", "SpaCy", "AWS"], "posted": "6 days ago", "type": "FULL_TIME"},
        {"id": 8, "title": "AI Software Engineer", "company": "Apple", "location": "Cupertino, CA", "remote": "ONSITE", "salary": "$175K-$250K", "score": 71, "status": "LOW_MATCH", "source": "LinkedIn", "skills": ["Swift", "Python", "CoreML", "ONNX"], "posted": "2 weeks ago", "type": "FULL_TIME"},
        {"id": 9, "title": "MLOps Engineer", "company": "Netflix", "location": "Los Gatos, CA", "remote": "REMOTE", "salary": "$165K-$230K", "score": 68, "status": "LOW_MATCH", "source": "Direct", "skills": ["Docker", "Kubernetes", "MLflow", "GCP"], "posted": "1 week ago", "type": "FULL_TIME"},
        {"id": 10, "title": "Deep Learning Engineer", "company": "Nvidia", "location": "Santa Clara, CA", "remote": "HYBRID", "salary": "$185K-$270K", "score": 65, "status": "LOW_MATCH", "source": "LinkedIn", "skills": ["CUDA", "PyTorch", "TensorRT", "C++"], "posted": "3 days ago", "type": "FULL_TIME"},
        {"id": 11, "title": "Data Analyst", "company": "Spotify", "location": "New York, NY", "remote": "HYBRID", "salary": "$95K-$130K", "score": 92, "status": "HIGH_MATCH", "source": "LinkedIn", "skills": ["Python", "SQL", "Tableau", "Pandas"], "posted": "1 day ago", "type": "FULL_TIME"},
        {"id": 12, "title": "GenAI Developer", "company": "StartupAI", "location": "Remote", "remote": "REMOTE", "salary": "$120K-$160K", "score": 88, "status": "ANALYZED", "source": "Wellfound", "skills": ["Python", "LangChain", "OpenAI", "FastAPI"], "posted": "12 hours ago", "type": "FULL_TIME"},
    ]
    return jobs

@st.cache_data
def get_demo_applications():
    apps = [
        {"id": 1, "job_title": "Senior ML Engineer", "company": "Google", "status": "APPLIED", "applied_date": "2026-09-10", "match_score": 94, "cover_letter": True},
        {"id": 2, "job_title": "AI Research Scientist", "company": "OpenAI", "status": "INTERVIEW", "applied_date": "2026-09-08", "match_score": 91, "cover_letter": True},
        {"id": 3, "job_title": "Data Scientist", "company": "Microsoft", "status": "PENDING_APPROVAL", "applied_date": None, "match_score": 87, "cover_letter": True},
        {"id": 4, "job_title": "LLM Engineer", "company": "Anthropic", "status": "PREPARING", "applied_date": None, "match_score": 85, "cover_letter": False},
        {"id": 5, "job_title": "Data Analyst", "company": "Spotify", "status": "APPLIED", "applied_date": "2026-09-12", "match_score": 92, "cover_letter": True},
        {"id": 6, "job_title": "GenAI Developer", "company": "StartupAI", "status": "SAVED", "applied_date": None, "match_score": 88, "cover_letter": False},
        {"id": 7, "job_title": "Computer Vision Engineer", "company": "Tesla", "status": "REJECTED", "applied_date": "2026-09-01", "match_score": 82, "cover_letter": True},
    ]
    return apps


# --- Sidebar ---
with st.sidebar:
    st.markdown("## 🤖 AI Job Agent")
    st.markdown("---")

    st.markdown("### ⚡ Quick Actions")
    if st.button("🔍 Run Job Discovery", use_container_width=True):
        st.toast("Scanning 3 job sources...", icon="🔍")
    if st.button("📊 Analyze Pending Jobs", use_container_width=True):
        st.toast("Analyzing 5 new jobs with AI...", icon="📊")
    if st.button("🚀 Prepare Applications", use_container_width=True):
        st.toast("Preparing cover letters & resume bullets...", icon="🚀")

    st.markdown("---")
    st.markdown("### ⚙️ Automation Settings")
    auto_discover = st.toggle("Auto-discover jobs", value=True)
    auto_analyze = st.toggle("AI job analysis", value=True)
    auto_prepare = st.toggle("Auto-prepare applications", value=False)
    st.caption("Human approval required before submission")

    st.markdown("---")
    st.markdown("### 🔗 Job Sources")
    sources = {
        "LinkedIn RSS": True,
        "Indeed API": True,
        "Wellfound": True,
        "RSS Feed": False,
    }
    for name, active in sources.items():
        status = "🟢" if active else "🔴"
        st.markdown(f"{status} {name}")

    st.markdown("---")
    st.markdown("### 📊 This Week")
    st.markdown(f"""
    - **12** new jobs discovered
    - **5** applications prepared
    - **2** interviews scheduled
    - **87%** avg match score
    """)


# --- Main Content ---
st.markdown("# 🤖 AI Job Application Automation Agent")
st.markdown("*Automated discovery, AI analysis, and intelligent application preparation with human-in-the-loop approval.*")

# --- KPI Metrics ---
jobs = get_demo_jobs()
apps = get_demo_applications()

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("📋 Jobs Tracked", "127", "+12 today")
col2.metric("🎯 High Matches", "18", "+3 new")
col3.metric("📝 Prepared", "5", "2 pending")
col4.metric("✅ Applied", "23", "+2 this week")
col5.metric("🎤 Interviews", "4", "1 upcoming")
col6.metric("📈 Avg Match", "84%", "+2.3%")

st.markdown("---")

# --- Tabs ---
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Job Board", "📊 Application Pipeline", "⚙️ Automation", "📈 Analytics", "👤 Profile"])

# ==================== TAB 1: JOB BOARD ====================
with tab1:
    col_search, col_filter = st.columns([3, 1])
    with col_search:
        search = st.text_input("🔍", placeholder="Search jobs by title, company, or skill...", label_visibility="collapsed")
    with col_filter:
        remote_filter = st.selectbox("Remote", ["All", "Remote", "Hybrid", "Onsite"], label_visibility="collapsed")

    filtered = jobs
    if search:
        q = search.lower()
        filtered = [j for j in filtered if q in j["title"].lower() or q in j["company"].lower() or any(q in s.lower() for s in j["skills"])]
    if remote_filter != "All":
        filtered = [j for j in filtered if j["remote"] == remote_filter.upper()]

    st.markdown(f"**{len(filtered)} jobs found**")

    for job in filtered:
        score_class = "match-high" if job["score"] >= 90 else ("match-medium" if job["score"] >= 75 else "match-low")
        status_class = {
            "HIGH_MATCH": "status-applied",
            "ANALYZED": "status-preparing",
            "LOW_MATCH": "status-rejected",
        }.get(job["status"], "status-new")

        skills_html = "".join([f'<span class="skill-tag">{s}</span>' for s in job["skills"]])

        st.markdown(f"""
        <div class="job-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <div class="job-title">{job['title']}</div>
                    <div class="job-company">{job['company']}</div>
                    <div class="job-meta">📍 {job['location']} · 🏠 {job['remote']} · 💰 {job['salary']} · 📅 {job['posted']}</div>
                    <div style="margin-top: 8px;">{skills_html}</div>
                </div>
                <div style="text-align: right;">
                    <span class="match-badge {score_class}">{job['score']}% match</span>
                    <div style="margin-top: 8px;">
                        <span class="status-badge {status_class}">{job['status'].replace('_', ' ').title()}</span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_a, col_b, col_c = st.columns([1, 1, 4])
        with col_a:
            if st.button(f"📝 Prepare", key=f"prep_{job['id']}", use_container_width=True):
                st.toast(f"Preparing application for {job['title']} at {job['company']}...", icon="📝")
        with col_b:
            if st.button(f"🔍 Analyze", key=f"analyze_{job['id']}", use_container_width=True):
                st.toast(f"Running AI analysis on {job['title']}...", icon="🔍")

# ==================== TAB 2: APPLICATION PIPELINE ====================
with tab2:
    st.markdown("### 📊 Application Pipeline")

    # Pipeline visualization
    pipeline_cols = st.columns(6)
    stages = [
        ("💾 Saved", 8, "var(--blue)"),
        ("⏳ Preparing", 3, "var(--yellow)"),
        ("👁️ Review", 2, "var(--orange)"),
        ("✅ Applied", 23, "var(--green)"),
        ("🎤 Interview", 4, "#a855f7"),
        ("🎉 Offer", 1, "var(--green)"),
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

    # Application list
    st.markdown("### 📋 Applications")

    app_filter = st.selectbox("Filter by status", ["All", "Pending Approval", "Applied", "Interview", "Saved", "Rejected"], label_visibility="collapsed")

    for app in apps:
        if app_filter != "All" and app["status"] != app_filter.replace(" ", "_").upper():
            continue

        status_map = {
            "APPLIED": ("status-applied", "✅ Applied"),
            "INTERVIEW": ("status-interview", "🎤 Interview"),
            "PENDING_APPROVAL": ("status-preparing", "👁️ Pending Review"),
            "PREPARING": ("status-new", "⏳ Preparing"),
            "SAVED": ("status-new", "💾 Saved"),
            "REJECTED": ("status-rejected", "❌ Rejected"),
        }
        status_class, status_label = status_map.get(app["status"], ("status-new", app["status"]))
        score_class = "match-high" if app["match_score"] >= 90 else ("match-medium" if app["match_score"] >= 75 else "match-low")

        st.markdown(f"""
        <div class="job-card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <div class="job-title">{app['job_title']}</div>
                    <div class="job-company">{app['company']}</div>
                    <div class="job-meta">
                        {'📅 Applied: ' + app['applied_date'] if app['applied_date'] else '⏳ Not yet applied'} · 
                        {'📝 Cover letter ready' if app['cover_letter'] else '📄 No cover letter'}
                    </div>
                </div>
                <div style="text-align: right;">
                    <span class="match-badge {score_class}">{app['match_score']}%</span>
                    <div style="margin-top: 6px;">
                        <span class="status-badge {status_class}">{status_label}</span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if app["status"] == "PENDING_APPROVAL":
            c1, c2, c3 = st.columns([1, 1, 4])
            with c1:
                if st.button("✅ Approve", key=f"approve_{app['id']}", use_container_width=True):
                    st.toast(f"Application for {app['job_title']} approved!", icon="✅")
            with c2:
                if st.button("✏️ Edit", key=f"edit_{app['id']}", use_container_width=True):
                    st.toast("Opening cover letter editor...", icon="✏️")

# ==================== TAB 3: AUTOMATION ====================
with tab3:
    st.markdown("### ⚙️ Automation Control Center")

    col_status, col_controls = st.columns([2, 1])

    with col_status:
        st.markdown("""
        <div class="job-card">
            <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
                <div style="width: 12px; height: 12px; background: #22c55e; border-radius: 50%; animation: pulse 2s infinite;"></div>
                <span style="color: var(--text-primary); font-weight: 600; font-size: 1.1rem;">Automation Active</span>
            </div>
            <div style="color: var(--text-secondary); font-size: 0.9rem;">
                <p>✅ Last discovery run: <strong>2 hours ago</strong> — found <strong>3 new jobs</strong></p>
                <p>✅ Last analysis batch: <strong>1 hour ago</strong> — analyzed <strong>8 jobs</strong></p>
                <p>✅ Last application prep: <strong>30 minutes ago</strong> — prepared <strong>2 applications</strong></p>
                <p>⏳ Next scheduled run: <strong>in 4 hours</strong></p>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_controls:
        st.markdown("#### 🎛️ Manual Controls")
        if st.button("🔄 Run Discovery Now", use_container_width=True):
            st.toast("Polling LinkedIn, Indeed, Wellfound...", icon="🔄")
        if st.button("🧠 Analyze All Pending", use_container_width=True):
            st.toast("Running AI analysis on 5 pending jobs...", icon="🧠")
        if st.button("📧 Prepare All Approved", use_container_width=True):
            st.toast("Generating cover letters and tailoring resumes...", icon="📧")

    st.markdown("---")
    st.markdown("### 📜 Recent Activity")

    activities = [
        ("🟢", "Job Discovered", "Senior ML Engineer at Google via LinkedIn", "2 hours ago"),
        ("🟢", "Job Discovered", "LLM Engineer at Anthropic via LinkedIn", "2 hours ago"),
        ("🟡", "AI Analysis Complete", "Data Scientist at Microsoft — 87% match", "1 hour ago"),
        ("🟡", "AI Analysis Complete", "LLM Engineer at Anthropic — 85% match", "1 hour ago"),
        ("🔵", "Application Prepared", "Senior ML Engineer at Google — cover letter ready", "30 min ago"),
        ("🟣", "Interview Scheduled", "AI Research Scientist at OpenAI — Sep 18", "1 day ago"),
        ("🟢", "Application Submitted", "Data Analyst at Spotify — applied via portal", "1 day ago"),
        ("🔴", "Rejected", "Computer Vision Engineer at Tesla", "3 days ago"),
    ]

    for icon, event_type, detail, time in activities:
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border);">
            <span style="font-size: 1.2rem;">{icon}</span>
            <div style="flex: 1;">
                <span style="color: var(--text-primary); font-weight: 500;">{event_type}</span>
                <span style="color: var(--text-muted);"> — {detail}</span>
            </div>
            <span style="color: var(--text-muted); font-size: 0.8rem;">{time}</span>
        </div>
        """, unsafe_allow_html=True)

# ==================== TAB 4: ANALYTICS ====================
with tab4:
    st.markdown("### 📈 Analytics Dashboard")

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("#### Match Score Distribution")
        fig_dist = px.bar(
            x=["90-100%", "75-89%", "50-74%", "0-49%"],
            y=[18, 35, 42, 32],
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
        fig_funnel = go.Figure(go.Funnel(
            y=["Discovered", "Matched", "Prepared", "Applied", "Interview", "Offer"],
            x=[127, 18, 5, 23, 4, 1],
            marker=dict(color=["#3b82f6", "#6366f1", "#eab308", "#22c55e", "#a855f7", "#22c55e"]),
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
        st.markdown("#### Jobs by Source")
        fig_source = px.pie(
            names=["LinkedIn", "Indeed", "Wellfound", "Direct", "RSS"],
            values=[45, 32, 18, 22, 10],
            template="plotly_dark",
            hole=0.4,
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
        st.markdown("#### Weekly Activity")
        fig_week = px.line(
            x=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            y=[8, 12, 6, 15, 10, 3, 2],
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

# ==================== TAB 5: PROFILE ====================
with tab5:
    st.markdown("### 👤 Profile & Resume")

    col_profile, col_resume = st.columns([1, 1])

    with col_profile:
        st.markdown("#### Personal Info")
        name = st.text_input("Full Name", value="Abdul Rehman")
        email = st.text_input("Email", value="a4rehman.ai@gmail.com")
        location = st.text_input("Location", value="Lahore, Pakistan")
        linkedin = st.text_input("LinkedIn", value="linkedin.com/in/abdul-rehman-ai001")
        github = st.text_input("GitHub", value="github.com/a4rehman")

        st.markdown("#### Target Preferences")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.selectbox("Job Type", ["Full-time", "Contract", "Part-time"])
            st.selectbox("Remote Preference", ["Remote", "Hybrid", "Onsite", "Any"])
        with col_t2:
            st.text_input("Min Salary (USD)", value="120000")
            st.text_input("Target Roles", value="ML Engineer, AI Engineer, Data Scientist")

    with col_resume:
        st.markdown("#### Skills")
        skills_text = st.text_area(
            "Your Skills (one per line)",
            value="Python\nTensorFlow\nPyTorch\nLangChain\nRAG\nMLOps\nDocker\nKubernetes\nSQL\nNLP\nComputer Vision\nLLMs",
            height=200,
        )

        st.markdown("#### Resume Upload")
        uploaded = st.file_uploader("Upload your resume (PDF)", type=["pdf"])
        if uploaded:
            st.success(f"✅ Uploaded: {uploaded.name}")
            st.markdown("**Parsed Summary:**")
            st.markdown("*AI Engineer with 1+ years of experience in ML, LLMs, and Agentic Systems. Skilled in Python, PyTorch, LangChain, and production deployment.*")

        st.markdown("#### Experience")
        st.text_area("Work Experience", value="""100Solutionz — Data Scientist (Internship)
Aug 2025 — Present
- Applied ML and NLP techniques to solve complex data challenges
- Collaborated with cross-functional teams on AI-driven solutions

Fiverr / Upwork — AI Engineer (Freelance)
Feb 2025 — Present
- Top Rated Seller delivering AI and Data Science solutions
- Served clients across 40+ countries""", height=150)

    if st.button("💾 Save Profile", use_container_width=True):
        st.toast("Profile saved! Job matching will use updated preferences.", icon="✅")
