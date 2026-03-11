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
    """Build the messages array for the chat completion."""
    messages = []

    # Add conversation history (last 10 messages)
    for msg in conversation_history[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Build context for the current query
    context_parts = []

    if condensed_notes:
        context_parts.append("=== DOCUMENTS ===")
        for note in condensed_notes:
            doc_note = note.get("note", {})
            parts = [f"\n--- {note.get('title', 'Untitled')} ---"]
            if doc_note.get("summary"):
                parts.append(f"Summary: {doc_note['summary']}")
            for section in doc_note.get("sections", []):
                heading = section.get("heading", "")
                content = section.get("content", "")
                pages = section.get("pages")
                page_str = f" [Pages {pages}]" if pages else ""
                if heading:
                    parts.append(f"\n## {heading}{page_str}\n{content}")
                elif content:
                    parts.append(f"\n{content}{page_str}")
            if doc_note.get("key_findings"):
                parts.append(f"\nKey findings: {json.dumps(doc_note['key_findings'], ensure_ascii=False)}")
            for table in doc_note.get("tables", []):
                desc = table.get("description", "")
                md = table.get("markdown", "")
                if desc or md:
                    parts.append(f"\nTable: {desc}\n{md}")
            context_parts.append("\n".join(parts))

    context_text = "\n".join(context_parts) if context_parts else "No relevant documents found."

    messages.append({
        "role": "user",
        "content": f"Document context:\n{context_text}\n\nUser question: {query}",
    })

    return messages
