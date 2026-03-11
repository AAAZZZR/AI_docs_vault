import asyncio
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.database import AsyncSessionLocal, get_db
from app.models.chat import ChatMessage
from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.services.llm import llm_service
from app.services.rag import rag_service

router = APIRouter()


@router.get("/messages", response_model=list[ChatMessageResponse])
async def get_messages(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get recent chat messages."""
    result = await db.execute(
        select(ChatMessage)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return [ChatMessageResponse.model_validate(msg) for msg in messages]


@router.post("/messages")
async def send_message(
    body: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a message and receive a streaming SSE response."""
    # Save user message
    user_msg = ChatMessage(role="user", content=body.content)
    db.add(user_msg)
    await db.flush()

    # Get recent history
    history_result = await db.execute(
        select(ChatMessage)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in reversed(history_result.scalars().all())
    ]

    # Parse intent
    intent = await asyncio.to_thread(
        llm_service.parse_chat_intent, body.content, history
    )

    # RAG query
    rag_context = await rag_service.query(
        db,
        intent.get("search_query", body.content),
        tag_filter=body.tag_filter,
    )

    async def generate():
        full_response = []

        # Real streaming: use a queue to bridge sync generator → async SSE
        import queue
        import threading

        token_queue: queue.Queue[str | None | Exception] = queue.Queue()
        cancel_event = threading.Event()

        def _stream_to_queue():
            try:
                for text in llm_service.generate_chat_response(
                    body.content,
                    rag_context["chunks"],
                    rag_context["condensed_notes"],
                    history,
                ):
                    if cancel_event.is_set():
                        break
                    token_queue.put(text)
            except Exception as e:
                token_queue.put(e)
            finally:
                token_queue.put(None)  # Sentinel

        thread = threading.Thread(target=_stream_to_queue, daemon=True)
        thread.start()

        stream_error = None
        while True:
            try:
                chunk = await asyncio.to_thread(token_queue.get, timeout=30)
            except Exception:
                break
            if chunk is None:
                break
            if isinstance(chunk, Exception):
                stream_error = chunk
                yield {
                    "event": "error",
                    "data": json.dumps({"message": str(chunk)}),
                }
                break
            full_response.append(chunk)
            yield {"event": "token", "data": json.dumps({"text": chunk})}

        # Signal thread to stop if client disconnected early
        cancel_event.set()

        # Build unique document references from chunks + condensed notes
        seen_ids = set()
        doc_refs = []
        for chunk in rag_context["chunks"]:
            doc_id = chunk.get("document_id")
            doc_title = chunk.get("document_title", "Unknown")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                doc_refs.append({"id": doc_id, "title": doc_title})
        for cn in rag_context["condensed_notes"]:
            doc_id = cn.get("document_id")
            if doc_id and doc_id not in seen_ids:
                seen_ids.add(doc_id)
                doc_refs.append({"id": doc_id, "title": cn["title"]})

        yield {
            "event": "references",
            "data": json.dumps({"documents": doc_refs}),
        }

        # Save assistant response (skip if error or empty)
        if stream_error or not full_response:
            yield {"event": "done", "data": ""}
            return

        async with AsyncSessionLocal() as save_db:
            assistant_msg = ChatMessage(
                role="assistant",
                content="".join(full_response),
                referenced_documents=rag_context["document_ids"],
            )
            save_db.add(assistant_msg)
            await save_db.commit()

        yield {"event": "done", "data": ""}

    return EventSourceResponse(generate())


@router.delete("/messages", status_code=204)
async def clear_messages(db: AsyncSession = Depends(get_db)):
    """Clear all chat history."""
    from sqlalchemy import delete
    await db.execute(delete(ChatMessage))
