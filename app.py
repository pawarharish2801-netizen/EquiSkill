"""
EquiSkill - GenAI Career Assistant
Streamlit front-end wired to the LangChain/Gemini agents in src/.

Run with:  streamlit run app.py
"""
import os
import streamlit as st

from src.config import get_api_key, get_flash_llm, get_pro_llm
from src.agents import LearningResourceAgent, InterviewAgent, ResumeMaker, JobSearch
from src.utils import save_markdown, extract_resume_text

st.set_page_config(page_title="EquiSkill - GenAI Career Assistant", page_icon="🎓", layout="centered")

MODE_LABELS = {
    "home": "🏠 Home",
    "tutorial": "📘 Tutorial Generator",
    "qa": "💬 Ask a GenAI Question",
    "interview_questions": "📝 Interview Question Prep",
    "mock_interview": "🎤 Mock Interview",
    "resume": "📄 Resume Builder",
    "jobs": "🔍 Job Search",
}

# ---------- Sidebar ----------
with st.sidebar:
    st.title("🎓 EquiSkill")
    st.caption("Free, open-source GenAI career mentor — aligned with UN SDG 4 (Quality Education), Target 4.4.")

    api_key_input = st.text_input(
        "Gemini API key",
        type="password",
        value=get_api_key() or "",
        help="Get a free key at https://aistudio.google.com/app/apikey. "
             "You can also set GOOGLE_API_KEY in a .env file instead of pasting it here.",
    )

    st.divider()
    mode = st.radio("Choose a mode", list(MODE_LABELS.keys()), format_func=lambda k: MODE_LABELS[k])
    st.divider()

    if st.button("🗑️ Clear this conversation", use_container_width=True):
        st.session_state.pop(f"history_{mode}", None)
        st.rerun()

    st.caption("Outputs are also saved as Markdown in `EquiSkill_output/` next to this app.")

if not api_key_input:
    st.warning("Add your Gemini API key in the sidebar to get started.")
    st.stop()

flash_llm = get_flash_llm(api_key_input)
pro_llm = get_pro_llm(api_key_input)

learning_agent = LearningResourceAgent(pro_llm, flash_llm)
interview_agent = InterviewAgent(pro_llm, flash_llm)
resume_maker = ResumeMaker(pro_llm)
job_search = JobSearch(pro_llm)

st.title(MODE_LABELS[mode])

if mode == "home":
    st.markdown("""
    Welcome to **EquiSkill**, your GenAI Career Assistant! Here is a simple guide to what you can do:

    *   **📘 Tutorial Generator:** Ask for a tutorial on any Generative AI topic, and it will build one with explanations and Python code.
    *   **💬 Ask a GenAI Question:** Ask general questions about Generative AI concepts or technologies.
    *   **📝 Interview Question Prep:** Get a curated list of interview questions for specific GenAI roles.
    *   **🎤 Mock Interview:** Practice your interview skills. The AI acts as the interviewer, asking one question at a time.
    *   **📄 Resume Builder:** Chat to provide your details, and it generates a professional LaTeX resume you can edit in Overleaf.
    *   **🔍 Job Search:** Simply enter a role and location to find recent job postings.

    👈 Select a mode from the sidebar to get started!
    """)
    st.stop()

history_key = f"history_{mode}"
if history_key not in st.session_state:
    st.session_state[history_key] = []  # list of langchain BaseMessage for chat modes

# ---------- Job search: single-shot form, not a chat ----------
if mode == "jobs":
    st.write("Tell me the role and location you're looking for.")
    query = st.text_input("e.g. 'Generative AI Engineer jobs in Pune, India'")
    if st.button("Search jobs", type="primary") and query:
        with st.spinner("Searching and formatting results..."):
            try:
                result_md = job_search.find_jobs(query)
                path = save_markdown(result_md, "Job_search")
                st.markdown(result_md)
                st.download_button("⬇️ Download as Markdown", result_md, file_name=os.path.basename(path))
            except RuntimeError as e:
                if "rate limits" in str(e).lower():
                    st.error("⚠️ **All available models have hit their daily rate limits.** "
                             "Please try again later or use a different API key.")
                else:
                    raise
            except Exception as e:
                err_msg = str(e).lower()
                if "timeout" in err_msg or "timed out" in err_msg:
                    st.warning("⚠️ **Web search timed out.** DuckDuckGo didn't respond in time. "
                               "Please try again — this is usually a temporary network issue.")
                else:
                    raise
    st.stop()

# ---------- Mock Interview: require resume upload first ----------
if mode == "mock_interview":
    if "mock_resume_text" not in st.session_state:
        st.info("📎 Please upload your resume to start the mock interview. "
                "The interviewer will tailor questions to your actual experience.")
        uploaded = st.file_uploader(
            "Upload your resume",
            type=["pdf", "docx", "txt"],
            key="mock_resume_upload",
        )
        if uploaded:
            with st.spinner("Reading your resume..."):
                text = extract_resume_text(uploaded)
            if text.startswith("(Could not"):
                st.error(text)
            else:
                st.session_state["mock_resume_text"] = text
                st.success(f"✅ Resume loaded ({len(text)} characters). You can now start the interview!")
                st.rerun()
        st.stop()
    else:
        with st.expander("📄 Loaded resume (click to view)", expanded=False):
            st.text(st.session_state["mock_resume_text"][:1500] + "..."
                    if len(st.session_state["mock_resume_text"]) > 1500
                    else st.session_state["mock_resume_text"])
        if st.button("🔄 Change resume", use_container_width=False):
            del st.session_state["mock_resume_text"]
            st.session_state.pop(history_key, None)
            st.rerun()

# ---------- Everything else: chat interface ----------
for msg in st.session_state[history_key]:
    role = "user" if msg.type == "human" else "assistant"
    with st.chat_message(role):
        st.markdown(msg.content)

placeholder_text = {
    "tutorial": "What GenAI topic should I write a tutorial about?",
    "qa": "What's your GenAI question?",
    "interview_questions": "What role or topic should I prep interview questions for?",
    "mock_interview": "Type 'I\'m ready' to begin, or answer the interviewer's last question.",
    "resume": "Tell me about the role you're targeting and your background.",
}[mode]

user_input = st.chat_input(placeholder_text)

if user_input:
    from langchain_core.messages import HumanMessage, AIMessage

    with st.chat_message("user"):
        st.markdown(user_input)

    history = st.session_state[history_key]

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                if mode == "tutorial":
                    reply = learning_agent.tutorial_step(history, user_input)
                elif mode == "qa":
                    reply = learning_agent.qa_step(history, user_input)
                elif mode == "interview_questions":
                    reply = interview_agent.questions_step(history, user_input)
                elif mode == "mock_interview":
                    resume_text = st.session_state.get("mock_resume_text", "")
                    reply = interview_agent.mock_interview_step(history, user_input, resume_text=resume_text)
                elif mode == "resume":
                    reply = resume_maker.step(history, user_input)
            except RuntimeError as e:
                if "rate limits" in str(e).lower():
                    reply = ("⚠️ **All available models have hit their daily rate limits.** "
                             "Please try again later or use a different API key. "
                             "Free-tier limits reset daily.")
                    st.error(reply)
                else:
                    raise
            except Exception as e:
                err_msg = str(e).lower()
                if "timeout" in err_msg or "timed out" in err_msg:
                    reply = ("⚠️ **Web search timed out.** DuckDuckGo didn't respond in time. "
                             "Please try again — this is usually a temporary network issue.")
                    st.warning(reply)
                else:
                    raise
        st.markdown(reply)

    history.append(HumanMessage(content=user_input))
    history.append(AIMessage(content=reply))
    st.session_state[history_key] = history

# ---------- LaTeX Resume PDF Generation (resume mode only) ----------
if mode == "resume" and len(st.session_state[history_key]) >= 4:
    st.divider()
    st.subheader("📄 Generate Professional PDF Resume")
    st.caption("Uses a professional LaTeX template (Jake's Resume). "
               "Your conversation details will be used to fill the template.")

    if st.button("🚀 Generate LaTeX Resume", type="primary", use_container_width=True):
        with st.spinner("Generating your LaTeX resume... This may take a moment."):
            try:
                from src.latex_resume import generate_resume_latex, get_overleaf_url

                latex_code = generate_resume_latex(
                    resume_maker.pro_llm,
                    st.session_state[history_key],
                )
                overleaf_url = get_overleaf_url(latex_code)

                st.session_state["resume_tex"] = latex_code
                st.session_state["resume_overleaf"] = overleaf_url
                st.success("✅ Resume generated successfully!")

            except RuntimeError as e:
                if "rate limits" in str(e).lower():
                    st.error("⚠️ All models hit their rate limits. Please try again later.")
                else:
                    st.error(f"Error generating resume: {e}")
            except Exception as e:
                st.error(f"Error generating resume: {e}")

    # Show LaTeX code + Overleaf link after generation
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
            overleaf_url = st.session_state.get("resume_overleaf", "")
            st.link_button("🌐 Open directly in Overleaf", overleaf_url, use_container_width=True)
        with col_b:
            st.download_button(
                "📥 Download .tex file",
                st.session_state["resume_tex"],
                file_name="resume.tex",
                mime="text/x-tex",
                use_container_width=True,
            )

        st.code(st.session_state["resume_tex"], language="latex")

# ---------- Save / export current thread ----------
if st.session_state[history_key]:
    transcript = "\n\n".join(
        f"**{'You' if m.type == 'human' else 'EquiSkill'}:** {m.content}"
        for m in st.session_state[history_key]
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save this session to file"):
            path = save_markdown(transcript, MODE_LABELS[mode].split(" ", 1)[1].replace(" ", "_"))
            st.success(f"Saved to {path}")
    with col2:
        st.download_button("⬇️ Download transcript", transcript, file_name=f"{mode}_session.md")
