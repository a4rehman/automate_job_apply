import sys
import os
import gradio as gr

# Add backend to sys.path so imports work correctly
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from app.main import app as fastapi_app

# Create a minimal Gradio UI to satisfy the Gradio SDK requirement
with gr.Blocks() as demo:
    gr.Markdown("# AI Job Application Automation Agent")
    gr.Markdown("The backend API is running. Access the API documentation at [**`/docs`**](/docs).")
    gr.Markdown("*(This UI is just a placeholder for the Hugging Face Gradio SDK)*")

# Mount the Gradio app onto the FastAPI app
app = gr.mount_gradio_app(fastapi_app, demo, path="/")
