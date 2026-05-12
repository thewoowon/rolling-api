from fastapi import APIRouter

from app.api.v1 import (
    admin,
    auth,
    event,
    feedback,
    health,
    host,
    matches,
    me,
    planner,
    profile,
    reports,
    rooms,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(matches.router, tags=["matches"])
api_router.include_router(feedback.router, tags=["feedback"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(event.router, prefix="/event", tags=["event"])
api_router.include_router(host.router, prefix="/host", tags=["host"])
api_router.include_router(planner.router, prefix="/planner", tags=["planner"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
