"""Async Groq LLM service wrapper for high-speed AI inference.

Provides a thin, production-ready abstraction over the Groq Cloud API
using ``groq.AsyncGroq``. Designed for ticket triage, summarization,
and context-augmented response generation.
"""

import logging
from typing import Optional

from groq import AsyncGroq, APIConnectionError, APIStatusError, APITimeoutError

from src.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMService:
    """Asynchronous Groq LLM client for structured text completion.

    Lazily initializes a single ``AsyncGroq`` client instance per
    ``LLMService`` object.  All inference calls are non-blocking.
    """

    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    FALLBACK_MODEL = "llama3-8b-8192"

    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        logger.info("[LLMService] Groq async client initialized.")

    # ── Inference ────────────────────────────────────────────────────

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a text completion from the Groq LLM.

        Parameters
        ----------
        prompt:
            The user-facing instruction or query.
        system_prompt:
            Optional system-level behavioural directive prepended to
            the message list.
        model:
            Model identifier (defaults to ``llama-3.3-70b-versatile``).
        temperature:
            Sampling temperature — lower values yield more deterministic
            outputs.
        max_tokens:
            Upper bound on the number of generated tokens.

        Returns
        -------
        str
            The model's text response content.

        Raises
        ------
        ConnectionError
            When the Groq API is unreachable or times out.
        RuntimeError
            For non-recoverable API errors (auth failures, rate limits).
        """
        model = model or self.DEFAULT_MODEL

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            chat_completion = await self._client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = chat_completion.choices[0].message.content
            logger.debug(
                "[LLMService] Completion received — model=%s, tokens=%s",
                model,
                chat_completion.usage.total_tokens if chat_completion.usage else "n/a",
            )
            return content or ""

        except APITimeoutError as exc:
            logger.error("[LLMService] Groq API request timed out: %s", exc)
            raise ConnectionError(
                "Groq API request timed out. Retry or check network connectivity."
            ) from exc

        except APIConnectionError as exc:
            logger.error("[LLMService] Unable to reach Groq API: %s", exc)
            raise ConnectionError(
                "Unable to connect to Groq API. Verify GROQ_API_KEY and network."
            ) from exc

        except APIStatusError as exc:
            logger.error(
                "[LLMService] Groq API status error %s: %s",
                exc.status_code,
                exc.message,
            )
            raise RuntimeError(
                f"Groq API error (HTTP {exc.status_code}): {exc.message}"
            ) from exc

    # ── Query Normalization ─────────────────────────────────────────

    async def normalize_query(self, raw_query: str) -> str:
        """Normalize a customer support query into a clean technical intent summary.

        Strips customer emotion, frustration, rants, typos, and slang to yield
        a concise, neutral technical search query (15 words or fewer) ideal
        for semantic vector similarity matching.

        Parameters
        ----------
        raw_query:
            The raw text from a customer ticket or search input.

        Returns
        -------
        str
            Normalized, neutral technical intent summary.
        """
        system_prompt = (
            "You are a technical query normalizer for an AI support system. "
            "Your task is to strip all customer emotion, rants, frustration, typos, and slang "
            "from the input text and extract only the core technical issue or query intent. "
            "Output MUST be a concise, neutral, clear statement of the technical issue in 15 words or fewer. "
            "Do NOT include conversational filler, preamble, quotes, or markdown formatting."
        )

        try:
            normalized = await self.generate_response(
                prompt=f"Normalize this query:\n\n{raw_query}",
                system_prompt=system_prompt,
                temperature=0.1,
                max_tokens=60,
            )
            clean_text = normalized.strip().strip('"').strip("'")
            logger.info("[LLMService] Query normalized successfully: '%s' -> '%s'", raw_query[:40], clean_text)
            return clean_text if clean_text else raw_query
        except Exception as exc:
            logger.warning("[LLMService] Query normalization failed, falling back to raw query: %s", exc)
            return raw_query.strip()

    # ── Connectivity ─────────────────────────────────────────────────

    async def ping(self) -> bool:
        """Send a minimal completion request to verify API connectivity.

        Returns ``True`` when the Groq API responds successfully,
        ``False`` otherwise.
        """
        try:
            await self._client.chat.completions.create(
                model=self.FALLBACK_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception as exc:
            logger.warning("[LLMService] Groq ping failed: %s", exc)
            return False
