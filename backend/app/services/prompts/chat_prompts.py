import json

CHAT_SYSTEM_PROMPT = """You are DocVault AI, an assistant that answers questions about the user's uploaded PDF documents.

RULES:
1. Answer ONLY based on the provided document context. Never make up information.
2. Cite your sources using the format: [Doc: Document Title]
3. When referencing specific pages, use: [Page X]
4. If the context doesn't contain enough information to answer, say:
   "I don't have enough information in your documents to answer this question."
5. Be concise but thorough. Prefer bullet points for multi-point answers.
6. If the user asks about a topic covered by multiple documents, synthesize across them.
7. When presenting data from tables, format them clearly.
8. Respond in the same language the user uses for their question."""


def build_intent_prompt(
    query: str, conversation_history: list[dict]
) -> str:
    history_str = ""
    if conversation_history:
        recent = conversation_history[-4:]
        history_str = "\n".join(
            f"{m['role']}: {m['content'][:200]}" for m in recent
        )

    return f"""Classify the user's query intent and extract search parameters.

Conversation history:
{history_str if history_str else "No previous messages"}

Current query: {query}

Return JSON:
{{
  "intent": "search | summarize | compare | list | follow_up",
  "search_query": "Optimized search query for vector similarity search",
  "entities": ["Key entities to look for"],
  "is_follow_up": true/false
}}

- "search": Looking for specific information
- "summarize": Wants a summary of document(s)
- "compare": Wants comparison between documents/entities
- "list": Wants a list of documents/tags
- "follow_up": Continuing from previous question

Respond with ONLY valid JSON."""


def build_chat_messages(
    query: str,
    context_chunks: list[dict],
    condensed_notes: list[dict],
    conversation_history: list[dict],
) -> list[dict]:
    """Build the messages array for the chat completion.

    Uses chunk-level context for precision, with document summaries for breadth.
    """
    messages = []

    # Add conversation history (last 10 messages)
    for msg in conversation_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Build context for the current query
    context_parts = []

    # Primary context: relevant chunks (high precision)
    if context_chunks:
        context_parts.append("=== RELEVANT PASSAGES ===")
        for chunk in context_chunks:
            doc_title = chunk.get("document_title", "Unknown")
            heading = chunk.get("heading", "")
            page_start = chunk.get("page_start")
            page_end = chunk.get("page_end")

            page_str = ""
            if page_start and page_end and page_start != page_end:
                page_str = f" [Pages {page_start}-{page_end}]"
            elif page_start:
                page_str = f" [Page {page_start}]"

            header = f"\n--- From: {doc_title}"
            if heading:
                header += f" > {heading}"
            header += f"{page_str} ---"

            context_parts.append(header)
            context_parts.append(chunk["content"])

    # Secondary context: document summaries (for breadth)
    if condensed_notes:
        context_parts.append("\n=== DOCUMENT SUMMARIES ===")
        for note in condensed_notes:
            doc_note = note.get("note", {})
            title = note.get("title", "Untitled")
            summary = doc_note.get("summary", "")
            key_findings = doc_note.get("key_findings", [])

            if summary:
                context_parts.append(f"\n--- {title} ---")
                context_parts.append(f"Summary: {summary}")
                if key_findings:
                    context_parts.append(
                        "Key findings: "
                        + json.dumps(key_findings, ensure_ascii=False)
                    )

    context_text = (
        "\n".join(context_parts)
        if context_parts
        else "No relevant documents found."
    )

    # Token budget control — truncate if context is too large (~4000 tokens ≈ 16000 chars)
    MAX_CONTEXT_CHARS = 16000
    if len(context_text) > MAX_CONTEXT_CHARS:
        context_text = context_text[:MAX_CONTEXT_CHARS] + "\n\n[Context truncated...]"

    messages.append({
        "role": "user",
        "content": f"Document context:\n{context_text}\n\nUser question: {query}",
    })

    return messages
