"""
Central config: loads env vars and builds LLM instances with automatic
model fallback.  When a model hits its rate limit (429 / ResourceExhausted),
the FallbackLLM transparently retries with the next model in the chain.
"""
import os
import logging
import streamlit as st
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model fallback chains — ordered by preference.
# Based on Google AI Studio free-tier rate limits (RPM / RPD):
#
# "Pro" chain (content generation: tutorials, resumes, job formatting):
#   Best quality first, highest-RPD model last as ultimate fallback.
#
# "Flash" chain (routing / categorization — lightweight tasks):
#   Highest-RPD model first so routing rarely fails.
# ---------------------------------------------------------------------------

PRO_MODELS = [
    "gemini-2.5-flash",       # 5 RPM / 20 RPD  — best quality flash
    "gemini-3-flash",         # 5 RPM / 20 RPD  — next-gen flash
    "gemini-3.5-flash",       # 5 RPM / 20 RPD  — latest flash
    "gemini-2.5-flash-lite",  # 10 RPM / 20 RPD — lighter, higher RPM
    "gemini-3.1-flash-lite",  # 15 RPM / 500 RPD — ultimate fallback
]

FLASH_MODELS = [
    "gemini-3.1-flash-lite",  # 15 RPM / 500 RPD — best for high-volume routing
    "gemini-2.5-flash",       # 5 RPM / 20 RPD
    "gemini-3-flash",         # 5 RPM / 20 RPD
    "gemini-3.5-flash",       # 5 RPM / 20 RPD
    "gemini-2.5-flash-lite",  # 10 RPM / 20 RPD
]

# Error phrases that signal a rate-limit / quota-exhaustion error
_RATE_LIMIT_MARKERS = (
    "429",
    "resource_exhausted",
    "resourceexhausted",
    "quota",
    "rate limit",
    "too many requests",
)


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True if *exc* looks like a rate-limit / quota error."""
    msg = str(exc).lower()
    return any(marker in msg for marker in _RATE_LIMIT_MARKERS)


class FallbackLLM(ChatGoogleGenerativeAI):
    """
    A drop-in replacement for ChatGoogleGenerativeAI that automatically
    falls back through a list of models when rate limits are hit.

    It subclasses ChatGoogleGenerativeAI so that LangChain functions
    that type-check (e.g. create_tool_calling_agent) keep working.
    The *first* model in the list is used to initialise the parent class;
    the remaining models are tried on 429 errors.
    """

    # Pydantic v2 — store our extras as class vars set after init
    _fallback_models: list = []
    _api_key: str = ""

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, models: list[str], api_key: str, temperature: float = 0.5):
        # Initialise the parent with the first (preferred) model
        super().__init__(
            model=models[0],
            temperature=temperature,
            google_api_key=api_key,
        )
        # Store the full chain for fallback
        object.__setattr__(self, "_fallback_models", models)
        object.__setattr__(self, "_api_key", api_key)
        object.__setattr__(self, "_temperature", temperature)

    def _build_llm(self, model_name: str) -> ChatGoogleGenerativeAI:
        """Create a plain ChatGoogleGenerativeAI for a specific model."""
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=self._temperature,
            google_api_key=self._api_key,
        )

    # ---- Override the core invoke / generate to add fallback logic --------

    def invoke(self, input, config=None, **kwargs):
        return self._invoke_with_fallback("invoke", input, config=config, **kwargs)

    def generate(self, messages, stop=None, callbacks=None, **kwargs):
        return self._generate_with_fallback(messages, stop=stop, callbacks=callbacks, **kwargs)

    def _invoke_with_fallback(self, method_name, *args, **kwargs):
        """Try each model in the fallback chain; re-raise if all fail."""
        last_exc = None
        for i, model_name in enumerate(self._fallback_models):
            try:
                if i == 0:
                    # Use self (the parent ChatGoogleGenerativeAI)
                    result = getattr(super(), method_name)(*args, **kwargs)
                else:
                    llm = self._build_llm(model_name)
                    result = getattr(llm, method_name)(*args, **kwargs)

                if i > 0:
                    # Notify user about the fallback
                    try:
                        st.toast(
                            f"⚡ Switched to **{model_name}** (model #{i+1})",
                            icon="🔄",
                        )
                    except Exception:
                        pass  # outside Streamlit context
                    logger.info("Fallback: %s -> %s succeeded", self._fallback_models[0], model_name)

                return result

            except Exception as exc:
                if _is_rate_limit_error(exc):
                    logger.warning(
                        "Rate limit hit on %s: %s — trying next model...",
                        model_name, exc,
                    )
                    try:
                        st.toast(
                            f"⏳ Rate limit hit on **{model_name}**, switching to next model...",
                            icon="⚠️",
                        )
                    except Exception:
                        pass
                    last_exc = exc
                    continue
                else:
                    raise  # non-rate-limit errors propagate immediately

        # All models exhausted
        raise RuntimeError(
            f"All {len(self._fallback_models)} models exhausted their rate limits. "
            f"Models tried: {', '.join(self._fallback_models)}. "
            f"Last error: {last_exc}"
        )

    def _generate_with_fallback(self, messages, **kwargs):
        """Fallback wrapper for the generate() path (used by agents)."""
        last_exc = None
        for i, model_name in enumerate(self._fallback_models):
            try:
                if i == 0:
                    result = super().generate(messages, **kwargs)
                else:
                    llm = self._build_llm(model_name)
                    result = llm.generate(messages, **kwargs)

                if i > 0:
                    try:
                        st.toast(
                            f"⚡ Switched to **{model_name}** (model #{i+1})",
                            icon="🔄",
                        )
                    except Exception:
                        pass
                    logger.info("Fallback: %s -> %s succeeded", self._fallback_models[0], model_name)

                return result

            except Exception as exc:
                if _is_rate_limit_error(exc):
                    logger.warning(
                        "Rate limit hit on %s: %s — trying next model...",
                        model_name, exc,
                    )
                    try:
                        st.toast(
                            f"⏳ Rate limit hit on **{model_name}**, switching to next model...",
                            icon="⚠️",
                        )
                    except Exception:
                        pass
                    last_exc = exc
                    continue
                else:
                    raise

        raise RuntimeError(
            f"All {len(self._fallback_models)} models exhausted their rate limits. "
            f"Models tried: {', '.join(self._fallback_models)}. "
            f"Last error: {last_exc}"
        )


# ---------------------------------------------------------------------------
# Public helpers (same signatures as before — drop-in replacement)
# ---------------------------------------------------------------------------

def get_api_key() -> str:
    """Reads the Gemini API key from env vars or Streamlit secrets."""
    key = os.getenv("GOOGLE_API_KEY")
    if not key:
        try:
            key = st.secrets["GOOGLE_API_KEY"]
        except Exception:
            key = None
    return key


def get_flash_llm(api_key: str) -> FallbackLLM:
    """Lightweight LLM chain for routing & categorization (high-RPD first)."""
    return FallbackLLM(models=FLASH_MODELS, api_key=api_key, temperature=0.5)


def get_pro_llm(api_key: str) -> FallbackLLM:
    """Stronger LLM chain for content generation (best-quality first)."""
    return FallbackLLM(models=PRO_MODELS, api_key=api_key, temperature=0.7)
