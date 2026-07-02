from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import admin, auth, courses, import_export, progress, questions, source_libraries, users


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="StudyForge API", version="0.4.0-alpha.1", lifespan=lifespan)
settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(questions.router)
app.include_router(progress.router)
app.include_router(import_export.router)
app.include_router(source_libraries.router)
