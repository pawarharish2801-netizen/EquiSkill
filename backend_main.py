"""
EquiSkill FastAPI Backend.

Exposes REST endpoints for every agent mode.
Streamlit (or any other frontend) calls these — no direct imports of src.agents needed.

Run with:  uvicorn backend_main:app --host 0.0.0.0 --port 8000 --reload
"""
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage

from src.config import get_flash_llm, get_pro_llm
from src.agents import LearningResourceAgent, InterviewAgent, ResumeMaker, JobSearch
from src.latex_resume import generate_resume_latex, get_overleaf_url
from src.utils import extract_resume_text
from src.database import create_tables, get_db, ChatSession, GeneratedResume

# -- Boot --
app = FastAPI(title="EquiSkill API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    create_tables()

# -- Shared LLM instances (one per process, not per request) --
_api_key = os.getenv("GOOGLE_API_KEY", "")
_flash   = get_flash_llm(_api_key)
_pro     = get_pro_llm(_api_key)

_learning  = LearningResourceAgent(_pro, _flash)
_interview = InterviewAgent(_pro, _flash)
_resume    = ResumeMaker(_pro)
_jobs      = JobSearch(_pro)


# ---------- Pydantic schemas ----------

class ChatRequest(BaseModel):
    user_input: str
    history: list[dict] = []   # [{"role": "human"|"ai", "content": "..."}]
    mode: str = "qa"

class JobSearchRequest(BaseModel):
    query: str

class MockInterviewRequest(BaseModel):
    user_input: str
    history: list[dict] = []
    resume_text: str = ""

class ResumeGenerateRequest(BaseModel):
    history: list[dict] = []


# ---------- Helpers ----------

def _deserialise_history(raw: list[dict]):
    msgs = []
    for m in raw:
        if m.get("role") == "human":
            msgs.append(HumanMessage(content=m["content"]))
        else:
            msgs.append(AIMessage(content=m["content"]))
    return msgs


def _save_chat(db: Session, mode: str, user_msg: str, ai_reply: str):
    db.add(ChatSession(mode=mode, user_msg=user_msg, ai_reply=ai_reply))
    db.commit()


# ---------- Endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat/tutorial")
def tutorial(req: ChatRequest, db: Session = Depends(get_db)):
    history = _deserialise_history(req.history)
    try:
        reply = _learning.tutorial_step(history, req.user_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    _save_chat(db, "tutorial", req.user_input, reply)
    return {"reply": reply}


@app.post("/api/chat/qa")
def qa(req: ChatRequest, db: Session = Depends(get_db)):
    history = _deserialise_history(req.history)
    try:
        reply = _learning.qa_step(history, req.user_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    _save_chat(db, "qa", req.user_input, reply)
    return {"reply": reply}


@app.post("/api/chat/interview-questions")
def interview_questions(req: ChatRequest, db: Session = Depends(get_db)):
    history = _deserialise_history(req.history)
    try:
        reply = _interview.questions_step(history, req.user_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    _save_chat(db, "interview_questions", req.user_input, reply)
    return {"reply": reply}


@app.post("/api/chat/mock-interview")
def mock_interview(req: MockInterviewRequest, db: Session = Depends(get_db)):
    history = _deserialise_history(req.history)
    try:
        reply = _interview.mock_interview_step(history, req.user_input, resume_text=req.resume_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    _save_chat(db, "mock_interview", req.user_input, reply)
    return {"reply": reply}


@app.post("/api/chat/resume")
def resume_chat(req: ChatRequest, db: Session = Depends(get_db)):
    history = _deserialise_history(req.history)
    try:
        reply = _resume.step(history, req.user_input)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    _save_chat(db, "resume", req.user_input, reply)
    return {"reply": reply}


@app.post("/api/resume/generate-latex")
def generate_latex(req: ResumeGenerateRequest, db: Session = Depends(get_db)):
    history = _deserialise_history(req.history)
    try:
        latex = generate_resume_latex(_pro, history)
        overleaf_url = get_overleaf_url(latex)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    db.add(GeneratedResume(latex_code=latex))
    db.commit()
    return {"latex": latex, "overleaf_url": overleaf_url}


@app.post("/api/jobs/search")
def job_search(req: JobSearchRequest):
    try:
        result = _jobs.find_jobs(req.query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"result": result}


@app.post("/api/resume/upload-parse")
async def upload_parse(file: UploadFile = File(...)):
    """Accepts an uploaded resume file and returns its extracted text."""
    try:
        text = extract_resume_text(file)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"text": text}
