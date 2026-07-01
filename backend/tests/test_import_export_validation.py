import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Course, Question
from app.services.course_exporter import export_course_pack
from app.services.course_importer import import_static_course_pack
from app.services.validation_service import validate_course_pack


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def make_static_pack(tmp_path: Path) -> Path:
    write_json(
        tmp_path / "course.json",
        {
            "id": "sample",
            "name": "Sample Course",
            "shortName": "SAMPLE",
            "version": "1.0",
            "description": "A compact test pack.",
            "topics": ["Identity", "Networks"],
        },
    )
    write_json(
        tmp_path / "sources.json",
        [
            {
                "id": "sample-src-1",
                "title": "Practice Assessment",
                "type": "Practice Test",
                "summary": "Imported test source.",
            }
        ],
    )
    write_json(
        tmp_path / "questions.json",
        [
            {
                "id": "sample-q1",
                "type": "single_choice",
                "topic": "Identity",
                "subtopic": "AAA",
                "difficulty": "Medium",
                "probability": 5,
                "sourceTags": ["Practice Test"],
                "sourceType": "Practice Test",
                "question": "Which AAA function decides what an authenticated user may access?",
                "choices": ["Authentication", "Authorization", "Accounting", "Attestation"],
                "answer": "Authorization",
                "explanation": "Authorization determines allowed access after identity is proven.",
                "memory": "Authorize access.",
                "examTip": "Do not confuse authentication with authorization.",
            }
        ],
    )
    write_json(
        tmp_path / "flashcards.json",
        [
            {
                "id": "sample-f1",
                "topic": "Identity",
                "front": "What does authorization decide?",
                "back": "Which resources an authenticated user can access.",
                "memory": "AuthZ = zones.",
            }
        ],
    )
    write_json(
        tmp_path / "glossary.json",
        [
            {
                "term": "Authorization",
                "topic": "Identity",
                "definition": "The process of granting access rights.",
                "examTip": "Comes after authentication.",
            }
        ],
    )
    write_json(
        tmp_path / "cheatsheets.json",
        [
            {
                "id": "sample-cs1",
                "title": "AAA Quick Compare",
                "topic": "Identity",
                "priority": 5,
                "content": [{"label": "Authorization", "value": "Access decisions"}],
            }
        ],
    )
    write_json(
        tmp_path / "mock-exams.json",
        [
            {
                "id": "sample-mock-1",
                "title": "Sample Mock",
                "questionCount": 1,
                "timeLimitMinutes": 5,
            }
        ],
    )
    return tmp_path


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_static_course_import_preserves_legacy_ids_and_exports_static_shape(tmp_path):
    pack_path = make_static_pack(tmp_path)
    db = make_session()

    result = import_static_course_pack(db, pack_path)

    course = db.query(Course).filter_by(course_code="sample").one()
    question = db.query(Question).filter_by(course_id=course.id).one()
    assert result["course_code"] == "sample"
    assert question.legacy_id == "sample-q1"
    assert question.status == "verified"
    assert question.oa_probability == 5
    assert question.confidence >= 8

    exported = export_course_pack(db, "sample")
    assert exported["course"]["id"] == "sample"
    assert exported["course"]["topics"] == ["Identity", "Networks"]
    assert exported["questions"][0]["id"] == "sample-q1"
    assert exported["questions"][0]["answer"] == "Authorization"
    assert exported["flashcards"][0]["id"] == "sample-f1"
    assert exported["sources"][0]["id"] == "sample-src-1"
    assert exported["mockExams"][0]["id"] == "sample-mock-1"


def test_validation_flags_question_quality_warnings():
    pack = {
        "course": {"id": "bad", "topics": ["Security"]},
        "questions": [
            {
                "id": "bad-q1",
                "type": "multi_select",
                "topic": "Security",
                "difficulty": 6,
                "probability": 0,
                "sourceTags": ["Generated"],
                "status": "generated",
                "confidence": 11,
                "question": "Which controls use MFA and TLS?",
                "choices": ["MFA", "TLS", "FTP"],
                "answer": "MFA",
                "explanation": "",
            },
            {
                "id": "bad-q1",
                "type": "matching",
                "topic": "Security",
                "difficulty": 3,
                "probability": 3,
                "question": "Match each control.",
                "choices": [],
                "answer": {},
                "explanation": "Needs malformed warning.",
                "sourceTags": [],
                "status": "",
                "confidence": 5,
            },
        ],
    }

    warnings = validate_course_pack(pack)

    assert any("Duplicate question ID" in warning for warning in warnings)
    assert any("multi_select answer must be an array" in warning for warning in warnings)
    assert any("probability should be between 1 and 5" in warning for warning in warnings)
    assert any("difficulty should be between 1 and 5" in warning for warning in warnings)
    assert any("confidence should be between 1 and 10" in warning for warning in warnings)
    assert any("missing explanation" in warning for warning in warnings)
    assert any("missing source" in warning for warning in warnings)
    assert any("missing lineage" in warning for warning in warnings)
    assert any("matching question is malformed" in warning for warning in warnings)


def test_validation_flags_generated_answer_leak_and_high_confidence():
    warnings = validate_course_pack(
        {
            "course": {"id": "leaky", "topics": ["Security"]},
            "questions": [
                {
                    "id": "leaky-q1",
                    "type": "single_choice",
                    "topic": "Security",
                    "difficulty": 2,
                    "probability": 3,
                    "sourceTags": ["Generated"],
                    "sourceType": "generated",
                    "status": "generated",
                    "confidence": 8,
                    "question": "Which option is least privilege?",
                    "choices": ["Least privilege", "Open access", "Implicit trust"],
                    "answer": "Least privilege",
                    "explanation": "Least privilege limits access.",
                    "lineage": {"sourceId": "src"},
                }
            ],
        }
    )

    assert any("generated stem includes exact answer phrase" in warning for warning in warnings)
    assert any("generated question confidence should not exceed 6" in warning for warning in warnings)
