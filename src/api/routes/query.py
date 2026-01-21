"""Query endpoint for semantic search."""

import logging

from fastapi import APIRouter, HTTPException, status

from config.settings import Settings
from src.search.semantic_search import semantic_search, SearchQuery
from src.memory.store_factory import create_vector_store
from src.memory.embeddings import OpenAIEmbeddingModel
from src.api.models.requests import QueryRequest
from src.api.models.responses import QueryResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_memory(request: QueryRequest):
    """Query the memory index using semantic search.
    
    This endpoint:
    1. Embeds the query using OpenAI
    2. Searches the vector store (Pinecone/FAISS)
    3. Returns relevant chunks
    4. Optionally synthesizes an answer using LLM
    
    Args:
        request: QueryRequest with query and filters
        
    Returns:
        QueryResponse with search results
        
    Raises:
        HTTPException: If query fails
    """
    logger.info(f"Query request: {request.query[:50]}...")
    
    try:
        settings = Settings()
        
        # Initialize vector store and embedder
        store = create_vector_store(settings)
        embedder = OpenAIEmbeddingModel(settings)
        
        # Convert request to SearchQuery
        search_query = SearchQuery(
            query=request.query,
            top_k=request.top_k,
            min_score=request.min_score,
            date=request.date,
            video_id=request.video_id,
            source_types=None,
            speaker_ids=request.speaker_ids
        )
        
        # Perform semantic search
        results = semantic_search(search_query, store, embedder)
        
        logger.info(f"Query returned {len(results)} results")
        
        # Optionally generate LLM answer (future enhancement)
        answer = None
        # if request.generate_answer:
        #     answer = synthesize_answer(request.query, results, settings)
        
        return QueryResponse(
            query=request.query,
            results=results,
            answer=answer,
            total_results=len(results)
        )
    
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )


__all__ = ["router"]
