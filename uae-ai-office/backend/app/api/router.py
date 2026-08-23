from fastapi import APIRouter

from app.modules.audit_log.router import router as audit_log_router
from app.modules.auth.router import router as auth_router
from app.modules.briefs.router import router as briefs_router
from app.modules.collaboration.router import router as collaboration_router
from app.modules.conversations.router import router as conversations_router
from app.modules.documents.router import router as documents_router
from app.modules.documents.search_router import router as search_router
from app.modules.health.router import router as health_router
from app.modules.projects.router import router as projects_router
from app.modules.reports.router import router as reports_router
from app.modules.support.router import router as support_router
from app.modules.tasks.router import router as tasks_router
from app.modules.tenancy.router import router as tenancy_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(tenancy_router)
api_router.include_router(audit_log_router)
api_router.include_router(projects_router)
api_router.include_router(documents_router)
api_router.include_router(search_router)
api_router.include_router(conversations_router)
api_router.include_router(briefs_router)
api_router.include_router(support_router)
api_router.include_router(collaboration_router)
api_router.include_router(tasks_router)
api_router.include_router(reports_router)

# Future modules (added in their respective implementation steps):
#   invitations (team management)

