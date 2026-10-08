"""Read-only technical review receipt; missing or incomplete publications return 503."""
from fastapi import APIRouter, HTTPException
from app.services.technical_review_receipt import ReviewReceiptUnavailable, load_review_receipt

router = APIRouter(prefix="/api/data-lake/foundation", tags=["Technical review receipt"])


@router.get("/review-receipt")
def review_receipt():
    try:
        return load_review_receipt()
    except ReviewReceiptUnavailable as error:
        raise HTTPException(503, detail=dict(code=error.code, state="UNAVAILABLE_OR_UNVERIFIED",
                            message="검증 완료된 기술검토 게시본을 읽을 수 없습니다. 승인 0으로 대체하지 않습니다.")) from error
