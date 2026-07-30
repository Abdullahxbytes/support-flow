"""Hybrid Autopilot Triage Service.

Coordinates RAG context assembly, Groq LLM decision synthesis, routing rule
evaluation, and PostgreSQL ticket state updates.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ticket import ExecutionTrack, TicketPriority, TicketStatus
from src.schemas.ticket import TicketResponse, TicketUpdate
from src.schemas.triage import AutopilotDecisionSchema, TriageResultResponse
from src.services.llm_service import LLMService
from src.services.rag_service import RAGService
from src.services.ticket import TicketService

logger = logging.getLogger(__name__)


class TriageService:
    """Service encapsulating end-to-end hybrid autopilot ticket triage."""

    def __init__(
        self,
        rag_service: Optional[RAGService] = None,
        llm_service: Optional[LLMService] = None,
    ) -> None:
        """Initialize triage service dependencies."""
        self.rag_service = rag_service or RAGService()
        self.llm_service = llm_service or LLMService()

    async def process_ticket_triage(
        self,
        db: AsyncSession,
        ticket_id: int,
    ) -> TriageResultResponse:
        """Execute RAG context retrieval, Groq decision synthesis, and update ticket state in PostgreSQL.

        Parameters
        ----------
        db:
            Async Database Session.
        ticket_id:
            Primary key ID of target ticket.

        Returns
        -------
        TriageResultResponse
            Detailed triage outcome payload including updated ticket object and LLM decision.
        """
        # 1. Fetch target ticket from database
        ticket = await TicketService.get_ticket_by_id(db, ticket_id)
        if not ticket:
            raise ValueError(f"Ticket with ID {ticket_id} not found")

        full_ticket_text = f"Title: {ticket.title}\n\nDescription: {ticket.description}"

        # ── AI Guardrails ────────────────────────────────────────────────
        from src.services.guardrail_service import GuardrailService
        guard_report = GuardrailService.sanitize_input(full_ticket_text)

        if guard_report["is_injection"]:
            logger.warning("[TriageService] Prompt injection flagged for Ticket #%d", ticket_id)
            fallback_decision = AutopilotDecisionSchema(
                suggested_response="Triage suspended. Input flagged by system security filters.",
                category="Security",
                recommended_priority=TicketPriority.HIGH,
                execution_track=ExecutionTrack.HUMAN_REVIEW,
                confidence_score=0.0,
                reasoning="Flagged by prompt injection guardrails.",
            )
            update_payload = TicketUpdate(
                status=TicketStatus.IN_PROGRESS,
                priority=TicketPriority.HIGH,
                execution_track=ExecutionTrack.HUMAN_REVIEW,
                ai_draft_response=fallback_decision.suggested_response,
                rag_confidence_score=0.0,
            )
            updated_ticket = await TicketService.update_ticket(
                db, ticket=ticket, ticket_in=update_payload
            )
            return TriageResultResponse(
                ticket=TicketResponse.model_validate(updated_ticket),
                decision=fallback_decision,
                normalized_query=full_ticket_text,
                chunks_retrieved=0,
                message=f"Ticket #{ticket_id} routed to HUMAN_REVIEW due to safety guardrails.",
            )

        sanitized_text = guard_report["sanitized_text"]

        try:
            # 2. Assemble RAG context from Qdrant Cloud vector search using sanitized text
            rag_context = await self.rag_service.assemble_context(
                ticket_text=sanitized_text,
                score_threshold=0.70,
            )

            # 3. Generate structured Groq LLM Autopilot Decision
            decision: AutopilotDecisionSchema = (
                await self.llm_service.generate_triage_decision(
                    prompt_context=rag_context["prompt_context"]
                )
            )

            # 4. Evaluate Routing Rules
            # High-confidence threshold check: confidence >= 0.85 AND relevant KB chunks exist
            is_automated_qualified = (
                decision.confidence_score >= 0.85
                and rag_context["has_relevant_knowledge"]
                and decision.execution_track in (ExecutionTrack.AUTOMATED, ExecutionTrack.AUTOPILOT)
            )

            if is_automated_qualified:
                target_track = ExecutionTrack.AUTOMATED
                target_status = TicketStatus.RESOLVED
                logger.info(
                    "[TriageService] Ticket #%d routed to AUTOMATED track (RESOLVED, confidence=%.2f)",
                    ticket_id,
                    decision.confidence_score,
                )
            else:
                target_track = ExecutionTrack.HUMAN_REVIEW
                target_status = TicketStatus.IN_PROGRESS
                logger.info(
                    "[TriageService] Ticket #%d routed to HUMAN_REVIEW track (IN_PROGRESS, confidence=%.2f)",
                    ticket_id,
                    decision.confidence_score,
                )

            # 5. Persist updated ticket attributes to PostgreSQL
            update_payload = TicketUpdate(
                status=target_status,
                priority=decision.recommended_priority,
                execution_track=target_track,
                ai_draft_response=decision.suggested_response,
                rag_confidence_score=decision.confidence_score,
            )

            updated_ticket = await TicketService.update_ticket(
                db, ticket=ticket, ticket_in=update_payload
            )

            return TriageResultResponse(
                ticket=TicketResponse.model_validate(updated_ticket),
                decision=decision,
                normalized_query=rag_context.get("normalized_query"),
                chunks_retrieved=len(rag_context.get("retrieved_chunks", [])),
                message=f"Ticket #{ticket_id} triaged successfully to {target_track.value}.",
            )

        except Exception as exc:
            logger.error(
                "[TriageService] Triage failure for Ticket #%d, applying fail-safe fallback: %s",
                ticket_id,
                exc,
            )

            # Fail-safe resilience fallback
            fallback_decision = AutopilotDecisionSchema(
                suggested_response=(
                    "Automatic triage could not complete due to a system error. "
                    "This ticket has been escalated for manual human review."
                ),
                category="Escalated",
                recommended_priority=TicketPriority.HIGH,
                execution_track=ExecutionTrack.HUMAN_REVIEW,
                confidence_score=0.0,
                reasoning=f"System triage error fallback: {str(exc)}",
            )

            update_payload = TicketUpdate(
                status=TicketStatus.IN_PROGRESS,
                priority=TicketPriority.HIGH,
                execution_track=ExecutionTrack.HUMAN_REVIEW,
                ai_draft_response=fallback_decision.suggested_response,
                rag_confidence_score=0.0,
            )

            updated_ticket = await TicketService.update_ticket(
                db, ticket=ticket, ticket_in=update_payload
            )

            return TriageResultResponse(
                ticket=TicketResponse.model_validate(updated_ticket),
                decision=fallback_decision,
                normalized_query=full_ticket_text,
                chunks_retrieved=0,
                message=f"Ticket #{ticket_id} routed to HUMAN_REVIEW via fail-safe resilience fallback.",
            )
