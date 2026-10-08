"""Evidence-based development progress; review is read-only and never grants approval."""
from fastapi import APIRouter, HTTPException
from app.core.config import settings
from app.services.development_stage_review import get_development_stage_review

router = APIRouter(prefix="/api/development-stages", tags=["Development stage review"])


@router.get("/review")
def review():
    try:
        return get_development_stage_review(settings.DEVELOPMENT_STAGES_ROOT)
    except (OSError, ValueError, TypeError):
        # Do not echo arbitrary local file contents or connection details.
        raise HTTPException(503, detail={
            "code": "DEVELOPMENT_STAGE_REVIEW_UNAVAILABLE",
            "state": "UNVERIFIED",
            "message": "개발 단계 검증 근거를 읽을 수 없습니다.",
            "mutation_performed": False,
        })
