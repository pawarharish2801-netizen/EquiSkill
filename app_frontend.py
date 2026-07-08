"""
EquiSkill - Streamlit Frontend (Decoupled from AI/LangChain).

This is the enterprise-architecture version of app.py.
All AI calls go through the FastAPI backend via HTTP requests.

Run with:  streamlit run app_frontend.py
Or via Docker:  docker-compose up
"""
import os
import streamlit as st
import requests

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="EquiSkill - GenAI Career Assistant", page_icon="🎓", layout="centered")

MODE_LABELS = {
    "home":               "🏠 Home",
    "tutorial":           "📘 Tutorial Generator",
    "qa":                 "💬 Ask a GenAI Question",
    "interview_questions":"📝 Interview Question Prep",
    "mock_interview":     "🎤 Mock Interview",
    "resume":             "📄 Resume Builder",
    "jobs":               "🔍 Job Search",
}

# ---------- Sidebar ----------
with st.sidebar:
    st.title("🎓 EquiSkill")
    st.caption("Free, open-source GenAI career mentor — UN SDG 4 (Quality Education), Target 4.4.")
    st.divider()
    mode = st.radio("Choose a mode", list(MODE_LABELS.keys()), format_func=lambda k: MODE_LABELS[k])
    st.divider()
    if st.button("🗑️ Clear this conversation", use_container_width=True):
        st.session_state.pop(f"history_{mode}", None)
        st.session_state.pop("mock_resume_text", None)
        st.rerun()
    st.caption("Outputs are also saved to the backend database.")


# ---------- Helper: call backend ----------
def _post(endpoint: str, payload: dict) -> dict:
    """Call the FastAPI backend; raise a user-friendly error on failure."""
    try:
        resp = requests.post(f"{BACKEND_URL}{endpoint}", json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.error("⚠️ **Cannot reach backend.** Make sure the FastAPI server is running.")
        st.stop()
    except requests.exceptions.Timeout:
        st.error("⚠️ **Request timed out.** The AI is taking too long — please try again.")
        st.stop()
    except requests.exceptions.HTTPError as e:
        detail = e.response.json().get("detail", str(e))
        if "rate limits" in detail.lower():
            st.error("⚠️ **All models hit their daily rate limits.** Please try again later.")
        else:
            st.error(f"Backend error: {detail}")
        st.stop()


def _history_to_payload(history):
    """Convert list of (role, content) tuples to JSON-serialisable list."""
    return [{"role": r, "content": c} for r, c in history]


# ---------- Home ----------
st.title(MODE_LABELS[mode])

if mode == "home":
    st.markdown("""
    Welcome to **EquiSkill**, your GenAI Career Assistant! Here is a simple guide to what you can do:

    *   **📘 Tutorial Generator:** Ask for a tutorial on any Generative AI topic, and it will build one with explanations and Python code.
    *   **💬 Ask a GenAI Question:** Ask general questions about Generative AI concepts or technologies.
    *   **📝 Interview Question Prep:** Get a curated list of interview questions for specific GenAI roles.
    *   **🎤 Mock Interview:** Upload your resume, then practice with an AI interviewer that knows your background.
    *   **📄 Resume Builder:** Chat to provide your details, and it generates a professional LaTeX resume you can edit in Overleaf.
    *   **🔍 Job Search:** Simply enter a role and location to find recent job postings.

    👈 Select a mode from the sidebar to get started!
    """)
    st.stop()


# ---------- Job search (single-shot form) ----------
if mode == "jobs":
    st.write("Tell me the role and location you're looking for.")
    query = st.text_input("e.g. 'Generative AI Engineer jobs in Pune, India'")
    if st.button("Search jobs", type="primary") and query:
        with st.spinner("Searching and formatting results..."):
            data = _post("/api/jobs/search", {"query": query})
        st.markdown(data["result"])
        st.download_button("⬇️ Download results", data["result"], file_name="job_search.md")
    st.stop()


# ---------- Mock Interview: require resume upload first ----------
history_key = f"history_{mode}"
if history_key not in st.session_state:
    st.session_state[history_key] = []   # list of (role, content) tuples

if mode == "mock_interview":
    if "mock_resume_text" not in st.session_state:
        st.info("📎 Please upload your resume to start the mock interview. "
                "The interviewer will tailor questions to your actual experience.")
        uploaded = st.file_uploader("Upload your resume", type=["pdf", "docx", "txt"], key="mock_resume_upload")
        if uploaded:
            with st.spinner("Reading your resume..."):
                try:
                    resp = requests.post(
                        f"{BACKEND_URL}/api/resume/upload-parse",
                        files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
                        timeout=30,
                    )
                    resp.raise_for_status()
                    text = resp.json()["text"]
                    st.session_state["mock_resume_text"] = text
                    st.success(f"✅ Resume loaded ({len(text)} characters). You can now start the interview!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to parse resume: {e}")
        st.stop()
    else:
        with st.expander("📄 Loaded resume (click to view)", expanded=False):
            txt = st.session_state["mock_resume_text"]
            st.text(txt[:1500] + "..." if len(txt) > 1500 else txt)
        if st.button("🔄 Change resume"):
            del st.session_state["mock_resume_text"]
            st.session_state.pop(history_key, None)
            st.rerun()


# ---------- Chat UI ----------
for role, content in st.session_state[history_key]:
    with st.chat_message(role):
        st.markdown(content)

placeholder_text = {
    "tutorial":            "What GenAI topic should I write a tutorial about?",
    "qa":                  "What's your GenAI question?",
    "interview_questions": "What role or topic should I prep interview questions for?",
    "mock_interview":      "Type 'I'm ready' to begin, or answer the interviewer's last question.",
    "resume":              "Tell me about the role you're targeting and your background.",
}[mode]

user_input = st.chat_input(placeholder_text)

ENDPOINT_MAP = {
    "tutorial":            "/api/chat/tutorial",
    "qa":                  "/api/chat/qa",
    "interview_questions": "/api/chat/interview-questions",
    "mock_interview":      "/api/chat/mock-interview",
    "resume":              "/api/chat/resume",
}

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)

    history = st.session_state[history_key]
    payload = {"user_input": user_input, "history": _history_to_payload(history)}
    if mode == "mock_interview":
        payload["resume_text"] = st.session_state.get("mock_resume_text", "")

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            data = _post(ENDPOINT_MAP[mode], payload)
        reply = data["reply"]
        st.markdown(reply)

    history.append(("user", user_input))
    history.append(("assistant", reply))
    st.session_state[history_key] = history


# ---------- LaTeX Resume (resume mode only) ----------
if mode == "resume" and len(st.session_state[history_key]) >= 4:
    st.divider()
    st.subheader("📄 Generate Professional PDF Resume")
    st.caption("Uses Jake's Resume LaTeX template. Your conversation details fill the template.")

    if st.button("🚀 Generate LaTeX Resume", type="primary", use_container_width=True):
        with st.spinner("Generating your LaTeX resume..."):
            payload = {"history": _history_to_payload(st.session_state[history_key])}
            data = _post("/api/resume/generate-latex", payload)
            st.session_state["resume_tex"] = data["latex"]
            st.session_state["resume_overleaf"] = data["overleaf_url"]
            st.success("✅ Resume generated successfully!")

    if "resume_tex" in st.session_state:
        st.markdown("### 📋 How to get your PDF:")
        st.markdown(
            "1. **Copy** the LaTeX code below\n"
            "2. **Open** [Overleaf](https://www.overleaf.com) (free) → New Blank Project\n"
            "3. **Paste** the code → it compiles automatically\n"
            "4. **Download** your PDF from Overleaf ✅"
        )
        col_a, col_b = st.columns(2)
        with col_a:
            st.link_button("🌐 Open directly in Overleaf", st.session_state["resume_overleaf"], use_container_width=True)
        with col_b:
            st.download_button("📥 Download .tex file", st.session_state["resume_tex"],
                               file_name="resume.tex", mime="text/x-tex", use_container_width=True)
        st.code(st.session_state["resume_tex"], language="latex")


# ---------- Save / export ----------
if st.session_state[history_key]:
    transcript = "\n\n".join(
        f"**{'You' if r == 'user' else 'EquiSkill'}:** {c}"
        for r, c in st.session_state[history_key]
    )
    st.download_button("⬇️ Download transcript", transcript, file_name=f"{mode}_session.md")
