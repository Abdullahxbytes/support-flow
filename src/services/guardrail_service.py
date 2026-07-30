"""AI Safety and Guardrail Service.

Provides PII redaction (emails, phone numbers, credit card numbers, API keys)
and prompt injection detection for incoming ticket inputs before sending them
to the LLM and Vector search database.
"""

import logging
import re
from typing import TypedDict

logger = logging.getLogger(__name__)


class GuardrailReport(TypedDict):
    """Report dictionary returned by the Guardrail Service."""

    sanitized_text: str
    has_pii: bool
    is_injection: bool
    injection_risk: str


class GuardrailService:
    """Service class for sanitizing and safeguarding LLM inputs."""

    # PII patterns
    EMAIL_REGEX = re.compile(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", re.IGNORECASE
    )
    PHONE_REGEX = re.compile(
        r"\b(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    )
    CREDIT_CARD_REGEX = re.compile(
        r"\b(?:\d[ -]*?){13,16}\b"
    )
    API_KEY_REGEX = re.compile(
        r"\b(?:api[_-]?key|secret|token|password|auth|private[_-]?key)\s*[:=]\s*[\"']?[a-zA-Z0-9_\-\.\~]{16,}[\"']?\b",
        re.IGNORECASE,
    )

    # Prompt injection patterns
    INJECTION_PATTERNS = [
        r"ignore\s+(?:all\s+)?previous\s+instructions",
        r"disregard\s+(?:all\s+)?earlier\s+instructions",
        r"system\s+prompt\s+override",
        r"forget\s+(?:all\s+)?your\s+instructions",
        r"you\s+are\s+now\s+an?\s+assistant\s+that",
        r"bypass\s+(?:the\s+)?safety\s+guidelines",
        r"instead\s+of\s+your\s+normal\s+instructions",
        r"translate\s+this\s+system\s+prompt",
    ]
    INJECTION_REGEX = re.compile(
        "|".join(INJECTION_PATTERNS), re.IGNORECASE
    )

    @classmethod
    def sanitize_input(cls, text: str) -> GuardrailReport:
        """Sanitize input string to redact PII and detect prompt injection.

        Parameters
        ----------
        text:
            The raw customer text from the ticket.

        Returns
        -------
        GuardrailReport
            Dictionary containing sanitized text and risk evaluation.
        """
        if not text:
            return {
                "sanitized_text": "",
                "has_pii": False,
                "is_injection": False,
                "injection_risk": "none",
            }

        sanitized = text
        has_pii = False

        # Redact Emails
        if cls.EMAIL_REGEX.search(sanitized):
            sanitized = cls.EMAIL_REGEX.sub("[REDACTED_EMAIL]", sanitized)
            has_pii = True

        # Redact Phones
        if cls.PHONE_REGEX.search(sanitized):
            sanitized = cls.PHONE_REGEX.sub("[REDACTED_PHONE]", sanitized)
            has_pii = True

        # Redact Credit Cards
        if cls.CREDIT_CARD_REGEX.search(sanitized):
            sanitized = cls.CREDIT_CARD_REGEX.sub("[REDACTED_CARD]", sanitized)
            has_pii = True

        # Redact API Keys / Credentials
        if cls.API_KEY_REGEX.search(sanitized):
            sanitized = cls.API_KEY_REGEX.sub("[REDACTED_KEY]", sanitized)
            has_pii = True

        # Detect Prompt Injection
        is_injection = False
        injection_risk = "none"

        if cls.INJECTION_REGEX.search(text):
            is_injection = True
            injection_risk = "high"
            logger.warning("[GuardrailService] Potential prompt injection detected in input!")

        return {
            "sanitized_text": sanitized,
            "has_pii": has_pii,
            "is_injection": is_injection,
            "injection_risk": injection_risk,
        }
