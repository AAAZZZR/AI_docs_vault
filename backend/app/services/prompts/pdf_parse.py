import json


def build_page_parse_prompt(
    page_num: int, total_pages: int, context: str = ""
) -> str:
    return f"""Analyze this PDF page image (page {page_num} of {total_pages}).
Extract all content into this JSON structure:

{{
  "page": {page_num},
  "summary": "Brief summary of what this page contains",
  "content": "Full text content extracted from the page",
  "key_entities": ["list of key named entities: people, companies, technologies, etc."],
  "tables": [
    {{
      "description": "What the table shows",
      "markdown": "| Column1 | Column2 |\\n|---------|---------|\\n| data | data |"
    }}
  ],
  "figures": [
    {{
      "description": "Description of any charts, diagrams, or images on this page"
    }}
  ],
  "section_heading": "If this page starts a new section, what is the heading? null otherwise"
}}

{f"Context from previous pages: {context}" if context else ""}

Respond with ONLY valid JSON. No markdown code fences. No additional text."""


def build_condensed_note_prompt(
    page_extractions: list[dict], filename: str
) -> str:
    pages_json = json.dumps(page_extractions, ensure_ascii=False, indent=2)
    return f"""You are given page-by-page extractions from a PDF document named "{filename}".
Synthesize ALL the page extractions below into a single structured condensed note.

Page extractions:
{pages_json}

Create a JSON condensed note with this exact structure:

{{
  "version": 1,
  "title": "Document title (inferred from content, not filename)",
  "summary": "2-3 sentence overview of the entire document",
  "document_type": "One of: research_paper, report, financial_report, textbook_chapter, presentation, legal_document, technical_manual, article, other",
  "language": "ISO 639-1 code (e.g., en, zh-TW, ja)",
  "detected_date": "Date mentioned in document (YYYY-MM-DD) or null",
  "sections": [
    {{
      "heading": "Section title",
      "content": "Key content from this section, synthesized across pages",
      "pages": [1, 2]
    }}
  ],
  "key_findings": [
    "Most important finding or takeaway #1",
    "Most important finding or takeaway #2"
  ],
  "tables": [
    {{
      "description": "What the table shows",
      "markdown": "Markdown table content",
      "page": 3
    }}
  ],
  "entities": {{
    "companies": ["Company names mentioned"],
    "people": ["People mentioned"],
    "locations": ["Places mentioned"],
    "amounts": ["Financial amounts or key numbers"],
    "technologies": ["Technologies, products, or technical terms"]
  }},
  "auto_tags": ["5-10 tags that best categorize this document for future retrieval"]
}}

Rules:
- Synthesize information across pages, don't just concatenate
- The summary should give someone a clear understanding without reading the document
- Key findings should be actionable insights, not generic statements
- Tags should be specific enough to be useful for filtering (e.g., "semiconductor" not "technology")
- Preserve all tables in markdown format
- Detect the primary language of the document

Respond with ONLY valid JSON. No markdown code fences."""


def build_tag_prompt(
    condensed_note: dict, existing_tags: list[dict]
) -> str:
    """Context-aware tag generation prompt.

    existing_tags is a list of {"name": str, "description": str} dicts.
    """
    note_json = json.dumps(condensed_note, ensure_ascii=False)[:4000]

    if existing_tags:
        tags_section = "\n".join(
            f"- {t['name']}" + (f": {t['description']}" if t.get('description') else "")
            for t in existing_tags
        )
    else:
        tags_section = "(No existing tags yet)"

    return f"""You are an intelligent document tagging system. Given the document analysis below and the existing tag library, generate tags for this document.

DOCUMENT ANALYSIS:
{note_json}

EXISTING TAG LIBRARY:
{tags_section}

RULES:
1. REUSE existing tags whenever semantically appropriate (similarity > 0.7). Use the exact same name.
2. Only create NEW tags when no existing tag covers the topic.
3. For each tag, provide:
   - name: concise tag name (2-4 words max)
   - description: one-sentence description of what this tag covers
   - confidence: 0.0-1.0, how certain this tag applies
   - level: "domain" (broad category, 1-2 per doc) or "topic" (specific, 2-5 per doc)
   - reuse: true if reusing an existing tag, false if new
4. Generate 3-8 tags total.
5. If you notice two existing tags that seem redundant or overlapping, suggest a merge.

Return a JSON object:
{{
  "tags": [
    {{"name": "Machine Learning", "description": "Documents about ML algorithms and techniques", "confidence": 0.95, "level": "domain", "reuse": true}},
    {{"name": "Transformer Architecture", "description": "Attention-based neural network architectures", "confidence": 0.88, "level": "topic", "reuse": false}}
  ],
  "merge_suggestions": [
    {{"tag_a": "Deep Learning", "tag_b": "DL", "reason": "Same concept, different abbreviation", "keep": "Deep Learning"}}
  ]
}}

Respond with ONLY valid JSON. No markdown code fences."""
