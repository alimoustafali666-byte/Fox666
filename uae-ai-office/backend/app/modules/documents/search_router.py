"""POST /v1/search -- a Step 10 test/verification endpoint for
retrieval quality, NOT the final Ask Your Business API (that's Step 11,
built on top of retrieval_service.search_by_query_text). Open to all
four roles (owner/admin/manager/member), unlike upload/process/index --
reading already-indexed company content is a read permission every
member already has elsewhere in this API.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.embeddings.exceptions import EmbeddingError
from app.core.exceptions import BadRequestError
from app.db.session import get_db
from app.modules.auth.dependencies import get_tenant_context
from app.modules.auth.service import TenantContext
from app.modules.documents import retrieval_service
from app.modules.documents.exceptions import SearchUnavailableError
from app.modules.documents.models import DOCUMENT_TYPES
from app.modules.documents.schemas import SearchRequest, SearchResponse, SearchResultItem

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search(
    data: SearchRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> SearchResponse:
    if data.top_k is not None and data.top_k > settings.retrieval_top_k_max:
        raise BadRequestError(f"top_k must not exceed {settings.retrieval_top_k_max}.")
    if data.document_type is not None and data.document_type not in DOCUMENT_TYPES:
        raise BadRequestError(f"document_type must be one of {sorted(DOCUMENT_TYPES)}.")

    try:
        results = retrieval_service.search_by_query_text(
            db,
            company_id=context.company_id,
            query=data.query,
            top_k=data.top_k,
            document_id=data.document_id,
            project_id=data.project_id,
            document_type=data.document_type,
        )
    except EmbeddingError as exc:
        raise SearchUnavailableError("Search is temporarily unavailable.") from exc

    return SearchResponse(
        items=[
            SearchResultItem(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                chunk_index=r.chunk_index,
                content=r.content,
                score=r.score,
                page_number=r.page_number,
                sheet_name=r.sheet_name,
                section_name=r.section_name,
                source_location=r.source_location,
            )
            for r in results
        ]
    )

