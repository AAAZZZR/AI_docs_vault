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

        def _stream():
            return list(
                llm_service.generate_chat_response(
                    body.content,
                    rag_context["chunks"],
                    rag_context["condensed_notes"],
                    history,
                )
            )

        chunks = await asyncio.to_thread(_stream)

        for chunk in chunks:
            full_response.append(chunk)
            yield {"event": "token", "data": json.dumps({"text": chunk})}

        # Send document references
        yield {
            "event": "references",
            "data": json.dumps({
                "documents": [
                    {"id": cn["document_id"], "title": cn["title"]}
                    for cn in rag_context["condensed_notes"]
                ]
            }),
        }

        # Save assistant response
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
