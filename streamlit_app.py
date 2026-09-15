import streamlit as st
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

st.set_page_config(page_title="AI Job Application Agent", page_icon="??", layout="wide")

st.markdown("""
# ?? AI Job Application Automation Agent

## Features
- **Automated job scraping** from multiple platforms
- **AI-powered resume tailoring** for each application
- **Smart cover letter generation** using LLMs
- **Application tracking dashboard**

## Tech Stack
- Python, FastAPI, Playwright
- OpenAI GPT for content generation
- SQLite for application tracking

## How to Run Locally
```bash
git clone https://github.com/a4rehman/automate_job_apply
cd automate_job_apply
pip install -r requirements.txt
python app.py
```

---
*Built by Abdul Rehman | AI Engineer*
""")
