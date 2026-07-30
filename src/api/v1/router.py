"""Aggregator router for version 1 API endpoints."""

from fastapi import APIRouter

from src.api.v1.endpoints import tickets, health, knowledge, analytics

api_router = APIRouter()

api_router.include_router(tickets.router, prefix="/tickets", tags=["Tickets"])
api_router.include_router(health.router, tags=["System"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge Base"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
