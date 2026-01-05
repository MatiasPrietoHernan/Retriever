# routes/search.py
from fastapi import APIRouter, HTTPException, Depends, Header
from models.Request import SearchRequest, SearchResponse, IngestsProperties
from services.hybrid_service import HybridSearchService
from services.ingest_service import ingest_properties
from lib.config import client, embeddings, sparse_embeddings
from lib.auth import verify_api_key
from fastapi.concurrency import run_in_threadpool
from utils.logger import logger
router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def search_properties(
    request: SearchRequest,
    company: str = Header(..., description="Company name for the collection"),
    authenticated: bool = Depends(verify_api_key)
):
    try:
        logger.info(f"🔍 Iniciando búsqueda... {request.query}")

        collections = await run_in_threadpool(client.get_collections)
        collections_names = [c.name for c in collections.collections]
        if company not in collections_names:
            logger.error(f"❌ Colección '{company}' no encontrada")
            raise HTTPException(status_code=404, detail=f"Collection '{company}' not found")
        search_service = HybridSearchService(
        client=client,
        embeddings=embeddings,
        sparse_embeddings=sparse_embeddings,
        collection=company
    )

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

        logger.info(f"✅ Búsqueda completada. Resultados encontrados: {len(results)} con la query: {request.query}")
        return SearchResponse(results=results, count=len(results))

    except Exception as e:
        logger.error(f"❌ Error en búsqueda: {e} para la query: {request.query} en la collection: {company}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk")
async def bulk_properties(
    request: IngestsProperties,
    authenticated: bool = Depends(verify_api_key)  
):
    """Bulk ingestion in qdrant - Protected endpoint"""
    try:
        logger.info(f"📦 Iniciando ingesta masiva para {request.company}")
        
        result = await run_in_threadpool(
            ingest_properties,
            company=request.company,
            api_key=request.tokko_api_key
        )
        
        logger.info(f"✅ Ingesta completada para {request.company}")
        return {"message": result, "company": request.company}
    
    except Exception as e:
        logger.error(f"❌ Error en ingesta para {request.company}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check público"""
    return {"status": "healthy"}

