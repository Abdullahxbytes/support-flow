"""Aggregator router for version 1 API endpoints."""

from fastapi import APIRouter

from src.api.v1.endpoints import tickets

api_router = APIRouter()

api_router.include_router(tickets.router, prefix="/tickets", tags=["Tickets"])
