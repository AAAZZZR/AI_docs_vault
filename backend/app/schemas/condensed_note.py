from pydantic import BaseModel


class CondensedNoteSection(BaseModel):
    heading: str
    content: str
    pages: list[int] = []


class CondensedNoteTable(BaseModel):
    description: str
    markdown: str
    page: int | None = None


class CondensedNoteFigure(BaseModel):
    caption: str
    page: int
    s3_key: str | None = None


class CondensedNoteEntity(BaseModel):
    companies: list[str] = []
    people: list[str] = []
    locations: list[str] = []
    amounts: list[str] = []
    technologies: list[str] = []


class CondensedNote(BaseModel):
    version: int = 1
    title: str
    summary: str
    document_type: str
    language: str = "en"
    detected_date: str | None = None
    sections: list[CondensedNoteSection] = []
    key_findings: list[str] = []
    figures: list[CondensedNoteFigure] = []
    tables: list[CondensedNoteTable] = []
    entities: CondensedNoteEntity = CondensedNoteEntity()
    auto_tags: list[str] = []
    image_references: list[dict] = []
    appendix: list[dict] = []
