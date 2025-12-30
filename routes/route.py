# routes/search.py
from fastapi import APIRouter, HTTPException, Depends
from models.Request import SearchRequest, SearchResponse
from services.hybrid_service import HybridSearchService
from lib.config import config, client, embeddings, sparse_embeddings
from lib.auth import verify_api_key
from fastapi.concurrency import run_in_threadpool

router = APIRouter()

search_service = HybridSearchService(
    client=client,
    embeddings=embeddings,
    sparse_embeddings=sparse_embeddings,
    collection=config["collection"]
)

@router.post("/search", response_model=SearchResponse)
async def search_properties(
    request: SearchRequest,
    authenticated: bool = Depends(verify_api_key)
):
    try:
        if request.tipo_operacion is not None or request.precio_max is not None:
            results = await run_in_threadpool(
                search_service.search_with_filters,
                query=request.query,
                tipo_operacion=request.tipo_operacion,
                precio_max=request.precio_max,
                limit=request.limit
            )
        else:
            results = await run_in_threadpool(
                search_service.search,
                query=request.query,
                limit=request.limit
            )

        return SearchResponse(results=results, count=len(results))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check público"""
    return {"status": "healthy", "collection": config["collection"]}