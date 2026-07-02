from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Role = Literal["admin", "instructor", "student"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    email: str | None = None
    role: Role
    is_active: bool


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    user: UserOut


class UserCreate(BaseModel):
    username: str
    display_name: str
    password: str = Field(min_length=6)
    email: str | None = None
    role: Role = "student"
    is_active: bool = True


class UserPatch(BaseModel):
    display_name: str | None = None
    email: str | None = None
    role: Role | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    password: str = Field(min_length=6)


class CourseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    course_code: str
    name: str
    short_name: str | None = None
    description: str
    version: str
    exam_type: str
    provider: str
    is_active: bool
    topics_json: list[str] = []


class CourseCreate(BaseModel):
    course_code: str
    name: str
    short_name: str | None = None
    description: str = ""
    version: str = "1.0"
    exam_type: str = "personal_study"
    provider: str = "StudyForge"
    is_active: bool = True
    topics: list[str] = []


class CoursePatch(BaseModel):
    name: str | None = None
    short_name: str | None = None
    description: str | None = None
    version: str | None = None
    exam_type: str | None = None
    provider: str | None = None
    is_active: bool | None = None
    topics: list[str] | None = None


class QuestionCreate(BaseModel):
    course_code: str | None = None
    course_id: int | None = None
    legacy_id: str | None = None
    question_type: str = "single_choice"
    topic: str = ""
    subtopic: str = ""
    difficulty: int = Field(default=3, ge=1, le=5)
    oa_probability: int = Field(default=3, ge=1, le=5)
    question_text: str
    choices: Any = Field(default_factory=list)
    answer: Any
    explanation: str = ""
    why_wrong: Any = Field(default_factory=dict)
    memory: str = ""
    exam_tip: str = ""
    status: str = "generated"
    confidence: int = Field(default=5, ge=1, le=10)
    lineage: dict[str, Any] = Field(default_factory=dict)


class QuestionPatch(BaseModel):
    question_type: str | None = None
    topic: str | None = None
    subtopic: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    oa_probability: int | None = Field(default=None, ge=1, le=5)
    question_text: str | None = None
    choices: Any | None = None
    answer: Any | None = None
    explanation: str | None = None
    why_wrong: Any | None = None
    memory: str | None = None
    exam_tip: str | None = None
    status: str | None = None
    confidence: int | None = Field(default=None, ge=1, le=10)
    lineage: dict[str, Any] | None = None


class AttemptCreate(BaseModel):
    selected_answer: Any | None = None
    selected_answer_json: Any | None = None
    is_correct: bool | None = None
    time_spent_seconds: int | None = None
    mode: str = "practice"


class BookmarkOut(BaseModel):
    id: str
    topic: str
    question: str
    date: str


class ReviewNoteCreate(BaseModel):
    note: str


class MockSessionCreate(BaseModel):
    started_at: str | None = None
    completed_at: str | None = None
    score_percent: int | None = None
    scorePct: int | None = None
    question_count: int | None = None
    questionCount: int | None = None
    passed_estimate: str | None = None
    passEstimate: str | None = None
    breakdown: Any = Field(default_factory=dict)
    topicBreakdown: Any = Field(default_factory=list)
    answers: Any = Field(default_factory=dict)
    review: Any = Field(default_factory=list)


class ImportPathRequest(BaseModel):
    path: str | None = None


class JsonCoursePackImport(BaseModel):
    bundle: dict[str, Any]


class SourceLibraryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    category: str = ""


class SourceLibraryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = None


class SourceLibraryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    category: str
    created_at: str
    updated_at: str


class SourceMaterialPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    source_type: str | None = None
    authority_level: int | None = Field(default=None, ge=1, le=5)
    confidence: str | None = None
    verification_status: str | None = None
    copyright_status: str | None = None
    original_url: str | None = None


class SourceMaterialOut(BaseModel):
    id: int
    library_id: int
    title: str
    source_type: str
    authority_level: int
    confidence: str
    verification_status: str
    copyright_status: str
    original_filename: str
    stored_path: str
    original_url: str
    checksum: str
    uploaded_by: int
    created_at: str
    updated_at: str


class SourceChunkOut(BaseModel):
    id: int
    source_id: int
    chunk_number: int
    page_number: int | None = None
    heading: str
    text: str
    checksum: str
    created_at: str


class SourceExtractionOut(BaseModel):
    source_id: int
    status: str
    message: str
    chunks: int
