from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    JSON,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, index=True, nullable=False)
    display_name = Column(String(160), nullable=False)
    email = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="student", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    attempts = relationship("QuestionAttempt", back_populates="user", cascade="all, delete-orphan")
    progress = relationship("UserCourseProgress", back_populates="user", cascade="all, delete-orphan")
    bookmarks = relationship("UserBookmark", back_populates="user", cascade="all, delete-orphan")
    mock_sessions = relationship("MockExamSession", back_populates="user", cascade="all, delete-orphan")
    review_notes = relationship("ReviewNote", back_populates="user", cascade="all, delete-orphan")


class Course(Base, TimestampMixin):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True)
    course_code = Column(String(80), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    short_name = Column(String(80), nullable=True)
    description = Column(Text, default="", nullable=False)
    version = Column(String(80), default="1.0", nullable=False)
    exam_type = Column(String(80), default="personal_study", nullable=False)
    provider = Column(String(160), default="StudyForge", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    topics_json = Column(JSON, default=list, nullable=False)
    legacy_mock_exams_json = Column(JSON, default=list, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    sources = relationship("Source", back_populates="course", cascade="all, delete-orphan")
    concepts = relationship("Concept", back_populates="course", cascade="all, delete-orphan")
    questions = relationship("Question", back_populates="course", cascade="all, delete-orphan")
    flashcards = relationship("Flashcard", back_populates="course", cascade="all, delete-orphan")
    glossary_terms = relationship("GlossaryTerm", back_populates="course", cascade="all, delete-orphan")
    cheat_sheets = relationship("CheatSheet", back_populates="course", cascade="all, delete-orphan")


class Source(Base, TimestampMixin):
    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("course_id", "legacy_id", name="uq_source_course_legacy"),)

    id = Column(Integer, primary_key=True)
    legacy_id = Column(String(120), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(255), nullable=False)
    source_type = Column(String(80), default="notes", nullable=False)
    confidence = Column(Integer, default=5, nullable=False)
    summary = Column(Text, default="", nullable=False)
    citation = Column(Text, default="", nullable=False)

    course = relationship("Course", back_populates="sources")
    questions = relationship("Question", back_populates="source")


class SourceLibrary(Base, TimestampMixin):
    __tablename__ = "source_libraries"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="", nullable=False)
    category = Column(String(120), default="", nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    materials = relationship("SourceMaterial", back_populates="library", cascade="all, delete-orphan")


class SourceMaterial(Base, TimestampMixin):
    __tablename__ = "source_materials"

    id = Column(Integer, primary_key=True)
    library_id = Column(Integer, ForeignKey("source_libraries.id"), nullable=False)
    title = Column(String(255), nullable=False)
    source_type = Column(String(80), nullable=False)
    authority_level = Column(Integer, default=3, nullable=False)
    confidence = Column(String(40), default="unverified", nullable=False)
    verification_status = Column(String(40), default="not_reviewed", nullable=False)
    copyright_status = Column(String(40), default="unknown", nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_path = Column(Text, nullable=False)
    original_url = Column(Text, default="", nullable=False)
    checksum = Column(String(64), unique=True, index=True, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    library = relationship("SourceLibrary", back_populates="materials")
    uploader = relationship("User")
    chunks = relationship("SourceChunk", back_populates="source", cascade="all, delete-orphan")
    import_jobs = relationship("SourceImportJob", back_populates="source", cascade="all, delete-orphan")


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (UniqueConstraint("source_id", "chunk_number", name="uq_source_chunk_number"),)

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("source_materials.id"), nullable=False)
    chunk_number = Column(Integer, nullable=False)
    page_number = Column(Integer, nullable=True)
    heading = Column(String(255), default="", nullable=False)
    text = Column(Text, nullable=False)
    checksum = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    source = relationship("SourceMaterial", back_populates="chunks")


class SourceImportJob(Base):
    __tablename__ = "source_import_jobs"

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("source_materials.id"), nullable=False)
    status = Column(String(40), default="pending", nullable=False)
    message = Column(Text, default="", nullable=False)
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    source = relationship("SourceMaterial", back_populates="import_jobs")


class Concept(Base, TimestampMixin):
    __tablename__ = "concepts"
    __table_args__ = (UniqueConstraint("course_id", "name", name="uq_concept_course_name"),)

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    name = Column(String(255), nullable=False)
    topic = Column(String(160), default="", nullable=False)
    subtopic = Column(String(160), default="", nullable=False)
    aliases_json = Column(JSON, default=list, nullable=False)
    related_concepts_json = Column(JSON, default=list, nullable=False)
    confidence = Column(Integer, default=5, nullable=False)

    course = relationship("Course", back_populates="concepts")
    questions = relationship("Question", back_populates="concept")
    flashcards = relationship("Flashcard", back_populates="concept")


class Question(Base, TimestampMixin):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("course_id", "legacy_id", name="uq_question_course_legacy"),)

    id = Column(Integer, primary_key=True)
    legacy_id = Column(String(120), nullable=True, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=True)
    question_type = Column(String(40), default="single_choice", nullable=False)
    topic = Column(String(160), default="", nullable=False)
    subtopic = Column(String(160), default="", nullable=False)
    difficulty = Column(Integer, default=3, nullable=False)
    oa_probability = Column(Integer, default=3, nullable=False)
    question_text = Column(Text, nullable=False)
    choices_json = Column(JSON, default=list, nullable=False)
    answer_json = Column(JSON, nullable=False)
    explanation = Column(Text, default="", nullable=False)
    why_wrong_json = Column(JSON, default=dict, nullable=False)
    memory = Column(Text, default="", nullable=False)
    exam_tip = Column(Text, default="", nullable=False)
    status = Column(String(40), default="generated", nullable=False)
    confidence = Column(Integer, default=5, nullable=False)
    lineage_json = Column(JSON, default=dict, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    course = relationship("Course", back_populates="questions")
    source = relationship("Source", back_populates="questions")
    concept = relationship("Concept", back_populates="questions")
    attempts = relationship("QuestionAttempt", back_populates="question", cascade="all, delete-orphan")
    bookmarks = relationship("UserBookmark", back_populates="question", cascade="all, delete-orphan")
    review_notes = relationship("ReviewNote", back_populates="question", cascade="all, delete-orphan")


class Flashcard(Base, TimestampMixin):
    __tablename__ = "flashcards"
    __table_args__ = (UniqueConstraint("course_id", "legacy_id", name="uq_flashcard_course_legacy"),)

    id = Column(Integer, primary_key=True)
    legacy_id = Column(String(120), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    concept_id = Column(Integer, ForeignKey("concepts.id"), nullable=True)
    topic = Column(String(160), default="", nullable=False)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    memory = Column(Text, default="", nullable=False)
    confidence = Column(Integer, default=5, nullable=False)

    course = relationship("Course", back_populates="flashcards")
    concept = relationship("Concept", back_populates="flashcards")


class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"
    __table_args__ = (UniqueConstraint("course_id", "term", name="uq_glossary_course_term"),)

    id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    term = Column(String(255), nullable=False)
    topic = Column(String(160), default="", nullable=False)
    definition = Column(Text, nullable=False)
    exam_tip = Column(Text, default="", nullable=False)
    related_terms_json = Column(JSON, default=list, nullable=False)
    confidence = Column(Integer, default=5, nullable=False)

    course = relationship("Course", back_populates="glossary_terms")


class CheatSheet(Base):
    __tablename__ = "cheat_sheets"
    __table_args__ = (UniqueConstraint("course_id", "legacy_id", name="uq_cheatsheet_course_legacy"),)

    id = Column(Integer, primary_key=True)
    legacy_id = Column(String(120), nullable=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    title = Column(String(255), nullable=False)
    topic = Column(String(160), default="", nullable=False)
    priority = Column(Integer, default=3, nullable=False)
    content_json = Column(JSON, default=list, nullable=False)
    confidence = Column(Integer, default=5, nullable=False)

    course = relationship("Course", back_populates="cheat_sheets")


class QuestionAttempt(Base):
    __tablename__ = "question_attempts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    selected_answer_json = Column(JSON, nullable=False)
    is_correct = Column(Boolean, default=False, nullable=False)
    time_spent_seconds = Column(Integer, nullable=True)
    mode = Column(String(40), default="practice", nullable=False)
    attempted_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="attempts")
    course = relationship("Course")
    question = relationship("Question", back_populates="attempts")


class UserCourseProgress(Base):
    __tablename__ = "user_course_progress"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_progress_user_course"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    mastery_percent = Column(Integer, default=0, nullable=False)
    readiness_score = Column(Integer, default=0, nullable=False)
    questions_answered = Column(Integer, default=0, nullable=False)
    correct_answers = Column(Integer, default=0, nullable=False)
    last_studied_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="progress")
    course = relationship("Course")


class UserBookmark(Base):
    __tablename__ = "user_bookmarks"
    __table_args__ = (UniqueConstraint("user_id", "question_id", name="uq_bookmark_user_question"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="bookmarks")
    course = relationship("Course")
    question = relationship("Question", back_populates="bookmarks")


class MockExamSession(Base):
    __tablename__ = "mock_exam_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    score_percent = Column(Integer, nullable=True)
    question_count = Column(Integer, default=0, nullable=False)
    passed_estimate = Column(String(80), nullable=True)
    breakdown_json = Column(JSON, default=dict, nullable=False)
    answers_json = Column(JSON, default=dict, nullable=False)

    user = relationship("User", back_populates="mock_sessions")
    course = relationship("Course")


class ReviewNote(Base):
    __tablename__ = "review_notes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="review_notes")
    question = relationship("Question", back_populates="review_notes")
