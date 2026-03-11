from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import chat, documents, tags, evolution

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev (host)
        "http://frontend:3000",    # Next.js dev (docker)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(
    documents.router,
    prefix=f"{settings.API_V1_PREFIX}/documents",
    tags=["Documents"],
)
app.include_router(
    tags.router,
    prefix=f"{settings.API_V1_PREFIX}/tags",
    tags=["Tags"],
)
app.include_router(
    chat.router,
    prefix=f"{settings.API_V1_PREFIX}/chat",
    tags=["Chat"],
)
app.include_router(
    evolution.router,
    prefix=f"{settings.API_V1_PREFIX}/evolution",
    tags=["Evolution"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "docvault-api"}
