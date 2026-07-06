from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Role = Literal["admin", "instructor", "student"]
ConceptStatus = Literal["generated", "reviewed", "verified", "rejected"]
ConceptConfidence = Literal["generated", "reviewed", "verified", "unverified"]
ConceptExtractionMethod = Literal["manual", "rule_based", "ai_disabled_stub"]
ConceptRelationshipType = Literal[
    "related_to",
    "contrasts_with",
    "depends_on",
    "belongs_to",
    "example_of",
    "component_of",
    "replaces",
    "maps_to",
]
SourceConflictType = Literal[
    "conflicting_definition",
    "conflicting_answer",
    "outdated_reference",
    "unsupported_claim",
    "duplicate_concept",
    "low_authority_source",
    "missing_lineage",
    "unclear_explanation",
    "possible_bad_answer",
]
SourceConflictSeverity = Literal["low", "medium", "high"]
SourceConflictStatus = Literal["generated", "needs_review", "reviewed", "resolved", "rejected"]
SourceConflictDetectionMethod = Literal["rule_based", "manual", "ai_disabled_stub"]
QuestionDraftStatus = Literal["generated", "needs_review", "reviewed", "verified", "rejected", "published"]
QuestionDraftConfidence = Literal["generated", "reviewed", "verified", "unverified"]
QuestionDraftGenerationMethod = Literal["manual", "rule_based", "ai_disabled_stub"]
QuestionDraftWarningSeverity = Literal["low", "medium", "high"]


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
    chunk_count: int = 0
    extraction_status: str = "not_extracted"
    extraction_message: str = ""
    conflict_count: int = 0
    unresolved_conflict_count: int = 0
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


class ConceptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    course_code: str | None = None
    status: ConceptStatus = "generated"
    confidence: ConceptConfidence = "unverified"
    aliases: list[str] = Field(default_factory=list)


class ConceptPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    course_code: str | None = None
    status: ConceptStatus | None = None
    confidence: ConceptConfidence | None = None
    aliases: list[str] | None = None


class ConceptOut(BaseModel):
    id: int
    name: str
    normalized_name: str
    description: str
    course_code: str | None = None
    status: ConceptStatus
    confidence: ConceptConfidence
    aliases: list[str] = Field(default_factory=list)
    source_count: int = 0
    relationship_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class ConceptAliasCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=255)


class ConceptAliasOut(BaseModel):
    id: int
    concept_id: int
    alias: str
    normalized_alias: str


class ConceptMergeRequest(BaseModel):
    target_concept_id: int


class ConceptMergeOut(BaseModel):
    source_concept: ConceptOut
    target_concept: ConceptOut
    aliases_moved: int
    source_links_moved: int
    relationships_moved: int


class SourceConceptLinkOut(BaseModel):
    id: int
    source_id: int
    source_chunk_id: int
    evidence_text: str
    confidence_score: float
    extraction_method: ConceptExtractionMethod
    created_at: str | None = None
    concept: ConceptOut


class ConceptSourceOut(BaseModel):
    id: int
    source_id: int
    source_title: str
    source_chunk_id: int
    chunk_number: int
    page_number: int | None = None
    heading: str
    evidence_text: str
    confidence_score: float
    extraction_method: ConceptExtractionMethod
    created_at: str | None = None


class ConceptEvidenceOut(BaseModel):
    id: int
    source_id: int
    source_title: str
    source_type: str
    source_confidence: str
    verification_status: str
    source_chunk_id: int
    chunk_number: int
    page_number: int | None = None
    heading: str
    evidence_text: str
    confidence_score: float
    extraction_method: ConceptExtractionMethod
    created_at: str | None = None


class ConceptExtractionOut(BaseModel):
    source_id: int
    status: str
    message: str
    concepts_created: int
    concepts_linked: int
    concepts: list[SourceConceptLinkOut]


class ConceptRelationshipCreate(BaseModel):
    concept_b_id: int
    relationship_type: ConceptRelationshipType
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    status: ConceptStatus = "generated"


class ConceptRelationshipPatch(BaseModel):
    concept_a_id: int | None = None
    concept_b_id: int | None = None
    relationship_type: ConceptRelationshipType | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    status: ConceptStatus | None = None


class ConceptRelationshipOut(BaseModel):
    id: int
    concept_a_id: int
    concept_a_name: str
    concept_b_id: int
    concept_b_name: str
    relationship_type: ConceptRelationshipType
    confidence_score: float
    status: ConceptStatus
    created_at: str | None = None


class SourceConflictPatch(BaseModel):
    conflict_type: SourceConflictType | None = None
    summary: str | None = None
    evidence_a: str | None = None
    evidence_b: str | None = None
    severity: SourceConflictSeverity | None = None
    status: SourceConflictStatus | None = None


class SourceConflictOut(BaseModel):
    id: int
    concept_id: int | None = None
    concept_name: str | None = None
    source_id_a: int | None = None
    source_title_a: str | None = None
    source_type_a: str | None = None
    source_authority_level_a: int | None = None
    source_confidence_a: str | None = None
    source_verification_status_a: str | None = None
    source_chunk_id_a: int | None = None
    source_chunk_number_a: int | None = None
    source_page_number_a: int | None = None
    source_id_b: int | None = None
    source_title_b: str | None = None
    source_type_b: str | None = None
    source_authority_level_b: int | None = None
    source_confidence_b: str | None = None
    source_verification_status_b: str | None = None
    source_chunk_id_b: int | None = None
    source_chunk_number_b: int | None = None
    source_page_number_b: int | None = None
    conflict_type: SourceConflictType
    summary: str
    evidence_a: str
    evidence_b: str
    severity: SourceConflictSeverity
    status: SourceConflictStatus
    detection_method: SourceConflictDetectionMethod
    created_at: str | None = None
    updated_at: str | None = None


class ConflictDetectionOut(BaseModel):
    target_type: str
    target_id: int
    conflicts_created: int
    conflicts: list[SourceConflictOut]


class QuestionDraftLineageCreate(BaseModel):
    source_id: int | None = None
    source_chunk_id: int | None = None
    concept_id: int | None = None
    evidence_text: str = ""
    lineage_reason: str = "manual"


class QuestionDraftLineageOut(BaseModel):
    id: int
    draft_id: int
    source_id: int | None = None
    source_title: str | None = None
    source_type: str | None = None
    source_authority_level: int | None = None
    source_confidence: str | None = None
    source_verification_status: str | None = None
    source_chunk_id: int | None = None
    source_chunk_number: int | None = None
    source_page_number: int | None = None
    concept_id: int | None = None
    concept_name: str | None = None
    concept_status: str | None = None
    evidence_text: str
    lineage_reason: str
    created_at: str | None = None


class QuestionDraftWarningOut(BaseModel):
    id: int | None = None
    draft_id: int | None = None
    code: str
    severity: QuestionDraftWarningSeverity
    message: str
    created_at: str | None = None


class QuestionPublishHistoryOut(BaseModel):
    id: int
    draft_id: int | None = None
    question_id: int
    course_code: str
    action: str
    previous_status: str | None = None
    new_status: str
    published_by: int | None = None
    notes: str = ""
    created_at: str | None = None


class QuestionDraftCreate(BaseModel):
    course_code: str = Field(min_length=1, max_length=80)
    source_id: int | None = None
    source_chunk_id: int | None = None
    concept_id: int | None = None
    question_type: str = "single_choice"
    stem: str = Field(min_length=1)
    choices: Any = Field(default_factory=list)
    correct_answer: Any = Field(default_factory=list)
    explanation: str = ""
    explanation_json: dict[str, Any] = Field(default_factory=dict)
    difficulty: int = Field(default=3, ge=1, le=5)
    oa_probability: int = Field(default=3, ge=1, le=5)
    status: QuestionDraftStatus = "needs_review"
    confidence: QuestionDraftConfidence = "generated"
    generation_method: QuestionDraftGenerationMethod = "manual"
    lineage: list[QuestionDraftLineageCreate] = Field(default_factory=list)


class QuestionDraftPatch(BaseModel):
    course_code: str | None = Field(default=None, min_length=1, max_length=80)
    source_id: int | None = None
    source_chunk_id: int | None = None
    concept_id: int | None = None
    question_type: str | None = None
    stem: str | None = Field(default=None, min_length=1)
    choices: Any | None = None
    correct_answer: Any | None = None
    explanation: str | None = None
    explanation_json: dict[str, Any] | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    oa_probability: int | None = Field(default=None, ge=1, le=5)
    status: QuestionDraftStatus | None = None
    confidence: QuestionDraftConfidence | None = None
    generation_method: QuestionDraftGenerationMethod | None = None
    lineage: list[QuestionDraftLineageCreate] | None = None


class QuestionDraftGenerationRequest(BaseModel):
    course_code: str | None = Field(default=None, max_length=80)
    source_material_ids: list[int] = Field(default_factory=list)
    concept_ids: list[int] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=100)


class QuestionDraftOut(BaseModel):
    id: int
    course_code: str
    source_id: int | None = None
    source_title: str | None = None
    source_type: str | None = None
    source_authority_level: int | None = None
    source_confidence: str | None = None
    source_verification_status: str | None = None
    source_chunk_id: int | None = None
    source_chunk_number: int | None = None
    concept_id: int | None = None
    concept_name: str | None = None
    concept_status: str | None = None
    published_question_id: int | None = None
    question_type: str
    stem: str
    choices: Any
    correct_answer: Any
    explanation: str
    explanation_json: dict[str, Any] = Field(default_factory=dict)
    difficulty: int
    oa_probability: int
    status: QuestionDraftStatus
    confidence: QuestionDraftConfidence
    generation_method: QuestionDraftGenerationMethod
    created_by: int
    created_at: str | None = None
    updated_at: str | None = None
    lineage: list[QuestionDraftLineageOut] = Field(default_factory=list)
    warnings: list[QuestionDraftWarningOut] = Field(default_factory=list)
    publish_history: list[QuestionPublishHistoryOut] = Field(default_factory=list)
    published_question_status: str | None = None


class QuestionDraftGenerationOut(BaseModel):
    target_type: str
    target_id: int | None = None
    drafts_created: int
    drafts: list[QuestionDraftOut]
