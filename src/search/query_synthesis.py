"""Query synthesis: single ChatGPT call to synthesize answer from retrieved chunks.

Per guideline: exactly one ChatGPT call during the chat/query flow, after semantic
retrieval has selected the top‑k relevant chunks. Uses only those chunks as context.
"""

from __future__ import annotations

import logging
from typing import List

from config.settings import Settings

from src.search.semantic_search import SearchResult

logger = logging.getLogger(__name__)


def synthesize_answer(
    query: str,
    results: List[SearchResult],
    settings: Settings,
) -> str:
    """Synthesize an answer using exactly one ChatGPT call over the retrieved chunks.

    Uses only the provided chunks as context. No external knowledge.

    Args:
        query: User's natural-language question.
        results: Top-k chunks from semantic search (vector store).
        settings: App settings (OpenAI key, model).

    Returns:
        Synthesized answer string. If no chunks, returns a short message without
        calling ChatGPT.
    """
    if not results:
        return "No relevant chunks found. Try a different query or check that content has been indexed."

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    model = getattr(settings, "llm_model", "gpt-4o") or "gpt-4o"

    context_parts = []
    for i, r in enumerate(results, 1):
        part = f"[Chunk {i}] (id={r.chunk_id})"
        if r.start_time is not None and r.end_time is not None:
            part += f" [{r.start_time:.0f}s–{r.end_time:.0f}s]"
        if r.date:
            part += f" date={r.date}"
        part += "\n" + (r.text or "")
        context_parts.append(part)

    context = "\n\n---\n\n".join(context_parts)

    system = """You are a helpful assistant. Answer the user's question using ONLY the provided context chunks from a video diary. Do not use external knowledge. If the context does not contain enough information, say so briefly. Be concise."""

    user = f"""Context chunks from semantic search:

{context}

---

User question: {query}

Provide a direct answer based only on the chunks above."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=1024,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        logger.warning("Query synthesis failed: %s", e)
        return f"Could not synthesize an answer: {e}. Here are {len(results)} relevant chunk(s) you can review."


__all__ = ["synthesize_answer"]
