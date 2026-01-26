"""Query endpoint for semantic search.

Per guideline: ChatGPT is used only (1) per-chunk summarization during processing,
and (2) here—exactly one call after retrieval to synthesize the answer from top-k chunks.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from config.settings import Settings
from src.search.semantic_search import semantic_search, SearchQuery
from src.search.query_synthesis import synthesize_answer
from src.memory.store_factory import create_vector_store
from src.memory.embeddings import OpenAIEmbeddingModel
from src.api.models.requests import QueryRequest
from src.api.models.responses import QueryResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_memory(request: QueryRequest):
    """Query the memory index and synthesize an answer.

    1. Semantic retrieval: embed query, retrieve top-k chunks from vector store.
    2. Exactly one ChatGPT call: synthesize answer using only those chunks as context.
    """
    logger.info(f"Query request: {request.query[:50]}...")

    try:
        settings = Settings()

        if not settings.pinecone_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Pinecone API key not configured. Vector store is unavailable."
            )
        if not settings.openai_api_key:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OpenAI API key not configured. Embeddings and synthesis unavailable."
            )

        try:
            store = create_vector_store(settings)
        except RuntimeError as e:
            logger.error(f"Failed to create vector store: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Vector store unavailable: {str(e)}"
            )

        try:
            embedder = OpenAIEmbeddingModel(settings)
        except Exception as e:
            logger.error(f"Failed to initialize embedder: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Embedding model unavailable: {str(e)}"
            )

        search_query = SearchQuery(
            query=request.query,
            top_k=request.top_k,
            min_score=request.min_score,
            date=request.date,
            video_id=request.video_id,
            source_types=None,
            speaker_ids=request.speaker_ids
        )

        results = semantic_search(search_query, store, embedder)
        logger.info(f"Query returned {len(results)} results")

        answer = synthesize_answer(request.query, results, settings)

        return QueryResponse(
            query=request.query,
            results=results,
            answer=answer,
            total_results=len(results)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )


__all__ = ["router"]
