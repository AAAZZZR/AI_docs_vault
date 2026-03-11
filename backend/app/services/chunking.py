"""
Chunking service — splits page extractions into semantic chunks for RAG.

Strategy: section-aware chunking
- Respects section boundaries from the LLM page extractions
- Merges small consecutive chunks
- Splits large chunks at paragraph boundaries
- Target: ~500-1000 tokens per chunk (roughly 2000-4000 chars)
"""

import logging
import re

logger = logging.getLogger(__name__)

# Target chunk sizes in characters (rough proxy for tokens: ~4 chars/token)
MIN_CHUNK_CHARS = 800    # ~200 tokens — merge if smaller
MAX_CHUNK_CHARS = 4000   # ~1000 tokens — split if larger
TARGET_CHUNK_CHARS = 2000  # ~500 tokens — ideal size


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for mixed content."""
    return len(text) // 4


def _split_at_paragraphs(text: str, max_chars: int) -> list[str]:
    """Split text at paragraph boundaries, respecting max size."""
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        if current and len(current) + len(para) + 2 > max_chars:
            chunks.append(current.strip())
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para

    if current.strip():
        chunks.append(current.strip())

    return chunks


def build_chunks_from_condensed_note(
    condensed_note: dict,
    page_extractions: list[dict],
) -> list[dict]:
    """
    Build semantic chunks from a condensed note + page extractions.

    Returns list of:
        {
            "content": str,
            "heading": str | None,
            "page_start": int | None,
            "page_end": int | None,
        }
    """
    chunks = []

    # Strategy 1: Use sections from condensed note (preferred — already synthesized)
    sections = condensed_note.get("sections", [])
    if sections:
        for section in sections:
            heading = section.get("heading", "")
            content = section.get("content", "")
            pages = section.get("pages", [])

            if not content or not content.strip():
                continue

            page_start = min(pages) if pages else None
            page_end = max(pages) if pages else None

            # Prepend heading to content for embedding context
            full_text = f"{heading}\n\n{content}" if heading else content

            if len(full_text) <= MAX_CHUNK_CHARS:
                chunks.append({
                    "content": full_text,
                    "heading": heading or None,
                    "page_start": page_start,
                    "page_end": page_end,
                })
            else:
                # Split large sections
                sub_chunks = _split_at_paragraphs(full_text, TARGET_CHUNK_CHARS)
                for i, sub in enumerate(sub_chunks):
                    chunks.append({
                        "content": sub,
                        "heading": f"{heading} (part {i + 1})" if heading else None,
                        "page_start": page_start,
                        "page_end": page_end,
                    })

    # Strategy 2: Fallback to page extractions if no sections
    if not chunks and page_extractions:
        for extraction in page_extractions:
            content = extraction.get("content", "") or extraction.get("summary", "")
            if not content or not content.strip():
                continue
            page_num = extraction.get("page")

            heading = extraction.get("section_heading")
            full_text = f"{heading}\n\n{content}" if heading else content

            if len(full_text) <= MAX_CHUNK_CHARS:
                chunks.append({
                    "content": full_text,
                    "heading": heading,
                    "page_start": page_num,
                    "page_end": page_num,
                })
            else:
                sub_chunks = _split_at_paragraphs(full_text, TARGET_CHUNK_CHARS)
                for i, sub in enumerate(sub_chunks):
                    chunks.append({
                        "content": sub,
                        "heading": f"Page {page_num} (part {i + 1})" if page_num else None,
                        "page_start": page_num,
                        "page_end": page_num,
                    })

    # Merge small consecutive chunks
    merged = []
    buffer = None
    for chunk in chunks:
        if buffer is None:
            buffer = chunk
            continue

        combined_len = len(buffer["content"]) + len(chunk["content"])
        if combined_len < MIN_CHUNK_CHARS:
            # Merge
            buffer["content"] = f"{buffer['content']}\n\n{chunk['content']}"
            if chunk.get("heading") and not buffer.get("heading"):
                buffer["heading"] = chunk["heading"]
            if chunk.get("page_end"):
                buffer["page_end"] = chunk["page_end"]
        else:
            merged.append(buffer)
            buffer = chunk

    if buffer:
        merged.append(buffer)

    # Add summary as first chunk (always useful for high-level queries)
    summary = condensed_note.get("summary", "")
    key_findings = condensed_note.get("key_findings", [])
    if summary:
        summary_text = f"Document Summary\n\n{summary}"
        if key_findings:
            summary_text += "\n\nKey Findings:\n" + "\n".join(
                f"- {f}" for f in key_findings
            )
        merged.insert(0, {
            "content": summary_text,
            "heading": "Document Summary",
            "page_start": None,
            "page_end": None,
        })

    # Add token estimates
    for chunk in merged:
        chunk["token_count"] = _estimate_tokens(chunk["content"])

    logger.info(
        "Built %d chunks (total ~%d tokens)",
        len(merged),
        sum(c["token_count"] for c in merged),
    )
    return merged
