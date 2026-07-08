"""
Agent classes for EquiSkill.

These mirror the notebook's LearningResourceAgent / InterviewAgent /
ResumeMaker / JobSearch classes, but every method is a single "step"
that takes the conversation so far + one new user message and returns
one AI response.

Search is done manually (not via tool-calling agents) to avoid
thought_signature compatibility issues with newer Gemini models.
"""
import os
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.utils import trim_conversation

# ---------------------------------------------------------------------------
# Tavily web search helper — called directly, not as an agent tool.
# ---------------------------------------------------------------------------

def _web_search(query: str, max_results: int = 5) -> str:
    """Run a Tavily web search and return formatted results."""
    try:
        from tavily import TavilyClient
        api_key = os.getenv("TAVILY_API_KEY", "")
        if not api_key:
            return "(Web search unavailable — TAVILY_API_KEY not set in .env)"
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=max_results, include_answer=True)
        parts = []
        if response.get("answer"):
            parts.append(f"Summary: {response['answer']}\n")
        for r in response.get("results", []):
            parts.append(f"- [{r.get('title', 'Link')}]({r.get('url', '')}): {r.get('content', '')[:200]}")
        return "\n".join(parts) if parts else "No results found."
    except Exception as e:
        return f"(Web search failed: {e})"


class LearningResourceAgent:
    """Handles GenAI tutorials (with web search) and open Q&A (plain chat)."""

    def __init__(self, pro_llm, flash_llm):
        self.pro_llm = pro_llm
        self.flash_llm = flash_llm

    def tutorial_step(self, chat_history, user_input: str) -> str:
        """One tutorial-generation turn. Searches the web first, then generates."""
        # Step 1: Search for relevant info
        search_results = _web_search(f"tutorial {user_input} generative AI")

        # Step 2: Generate tutorial using search results as context
        system_message = (
            "You are a knowledgeable Senior Generative AI Developer and experienced "
            "blogger who writes high-quality tutorials on Generative AI. "
            "Produce a well-structured tutorial in Markdown with clear explanations, "
            "working Python code with comments, and reference links at the end. "
            "If the user is continuing a previous tutorial request, build on that context.\n\n"
            f"Here are some recent web search results for reference:\n{search_results}"
        )
        messages = [SystemMessage(content=system_message)] + list(chat_history) + [HumanMessage(content=user_input)]
        messages = trim_conversation(messages)
        response = self.pro_llm.invoke(messages)
        return response.content.replace("```markdown", "").strip()

    def qa_step(self, chat_history, user_input: str) -> str:
        """One Q&A turn. Plain chat model, no search needed."""
        system_message = (
            "You are an expert Generative AI Engineer with extensive experience training "
            "and guiding others in AI engineering. Provide insightful, clear answers to the "
            "user's question, referencing the conversation so far as needed."
        )
        messages = [SystemMessage(content=system_message)] + list(chat_history) + [HumanMessage(content=user_input)]
        messages = trim_conversation(messages)
        response = self.flash_llm.invoke(messages)
        return response.content


class InterviewAgent:
    """Handles interview-question lists (with web search) and mock interviews (plain chat)."""

    def __init__(self, pro_llm, flash_llm):
        self.pro_llm = pro_llm
        self.flash_llm = flash_llm

    def questions_step(self, chat_history, user_input: str) -> str:
        """One turn generating interview questions, with web search for references."""
        # Step 1: Search for relevant interview questions
        search_results = _web_search(f"interview questions {user_input} generative AI")

        # Step 2: Generate curated question list
        system_message = (
            "You are a skilled researcher who finds interview questions for Generative AI "
            "roles. Provide a curated list of relevant questions with references or links "
            "where possible, formatted in Markdown. Ask a clarifying question if the request "
            "is too vague.\n\n"
            f"Here are some recent web search results for reference:\n{search_results}"
        )
        messages = [SystemMessage(content=system_message)] + list(chat_history) + [HumanMessage(content=user_input)]
        messages = trim_conversation(messages)
        response = self.flash_llm.invoke(messages)
        return response.content.replace("```markdown", "").strip()

    def mock_interview_step(self, chat_history, user_input: str, resume_text: str = "") -> str:
        """One turn of a simulated interview. Uses the candidate's resume if provided."""
        resume_section = (
            f"\n\nThe candidate has uploaded their resume. Use it to ask targeted, "
            f"personalised questions based on their actual experience, skills, and projects.\n"
            f"--- CANDIDATE RESUME ---\n{resume_text}\n--- END RESUME ---"
            if resume_text else ""
        )
        system_message = (
            "You are a senior Generative AI Interviewer conducting a mock interview for a "
            "Generative AI / ML engineering role. "
            "Ask one question at a time. React naturally to the candidate's answer "
            "(acknowledge good points, probe weak areas). "
            "Keep the session focused (aim for 15-20 minutes overall). "
            "If the candidate says 'exit' or asks for feedback, provide a short "
            "performance evaluation instead of another question."
            + resume_section
        )
        messages = [SystemMessage(content=system_message)] + list(chat_history) + [HumanMessage(content=user_input)]
        messages = trim_conversation(messages)
        response = self.flash_llm.invoke(messages)
        return response.content


class ResumeMaker:
    """Conversational resume builder."""

    def __init__(self, pro_llm):
        self.pro_llm = pro_llm

    def step(self, chat_history, user_input: str) -> str:
        system_message = (
            "You are a skilled resume expert experienced in crafting resumes for tech "
            "roles, especially AI and Generative AI. Ask the user for necessary details "
            "(skills, experience, projects, target role) step by step across a few turns, "
            "then produce a complete resume template in Markdown with trending GenAI "
            "keywords once you have enough information."
        )
        messages = [SystemMessage(content=system_message)] + list(chat_history) + [HumanMessage(content=user_input)]
        messages = trim_conversation(messages)
        response = self.pro_llm.invoke(messages)
        return response.content.replace("```markdown", "").strip()


class JobSearch:
    """One-shot job search: runs a web search, then asks the LLM to format results."""

    def __init__(self, pro_llm):
        self.pro_llm = pro_llm

    def find_jobs(self, query: str) -> str:
        raw_results = _web_search(query, max_results=8)
        prompt = ChatPromptTemplate.from_template(
            "Your task is to turn the following raw search results about job "
            "listings into a clean, easy-to-read Markdown summary. Include company "
            "name, job title, and links where available. Content: {result}"
        )
        chain = prompt | self.pro_llm
        response = chain.invoke({"result": raw_results})
        return str(response.content).replace("```markdown", "").strip()
