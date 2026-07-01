from typing import Any


REQUIRED_QUESTION_FIELDS = ["id", "topic", "difficulty", "probability", "question", "answer", "explanation"]


def _question_id(question: dict[str, Any], index: int) -> str:
    return str(question.get("id") or f"question {index + 1}")


def _answer_in_choices(question: dict[str, Any]) -> bool:
    choices = question.get("choices")
    answer = question.get("answer")
    if not isinstance(choices, list) or not choices:
        return False
    if isinstance(answer, list):
        return all(item in choices for item in answer)
    if isinstance(answer, dict):
        return True
    return answer in choices


def validate_course_pack(pack: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    questions = pack.get("questions") or []
    ids: set[str] = set()
    duplicates: set[str] = set()

    for index, question in enumerate(questions):
        qid = _question_id(question, index)
        for field in REQUIRED_QUESTION_FIELDS:
            if question.get(field) in (None, "", []):
                warnings.append(f"Question {qid} is missing required field {field}.")

        if question.get("id"):
            if question["id"] in ids:
                duplicates.add(str(question["id"]))
            ids.add(str(question["id"]))

        qtype = question.get("type") or question.get("questionType") or "single_choice"
        choices = question.get("choices")
        if qtype in {"single_choice", "diagram"}:
            if not isinstance(choices, list) or len(choices) < 2:
                warnings.append(f"Question {qid} should have at least two choices.")
            elif not _answer_in_choices(question):
                warnings.append(f"Question {qid} answer is not present in choices.")

        if qtype == "multi_select":
            if not isinstance(question.get("answer"), list):
                warnings.append(f"Question {qid} multi_select answer must be an array.")
            elif not _answer_in_choices(question):
                warnings.append(f"Question {qid} multi_select answer contains values not present in choices.")

        if qtype == "matching":
            choices_valid = isinstance(choices, dict) and isinstance(choices.get("left"), list) and isinstance(choices.get("right"), list)
            answer_valid = isinstance(question.get("answer"), dict) and bool(question.get("answer"))
            if not choices_valid or not answer_valid:
                warnings.append(f"Question {qid} matching question is malformed.")

        if qtype == "ordering":
            if not isinstance(choices, list) or not isinstance(question.get("answer"), list):
                warnings.append(f"Question {qid} ordering question is malformed.")

        probability = question.get("probability")
        if not isinstance(probability, int) or probability < 1 or probability > 5:
            warnings.append(f"Question {qid} probability should be between 1 and 5.")

        difficulty = question.get("difficulty")
        if not isinstance(difficulty, int) or difficulty < 1 or difficulty > 5:
            warnings.append(f"Question {qid} difficulty should be between 1 and 5.")

        confidence = question.get("confidence")
        if confidence is None or not isinstance(confidence, int) or confidence < 1 or confidence > 10:
            warnings.append(f"Question {qid} confidence should be between 1 and 10.")
        if question.get("status") == "generated" and isinstance(confidence, int) and confidence > 6:
            warnings.append(f"Question {qid} generated question confidence should not exceed 6.")

        if not question.get("explanation"):
            warnings.append(f"Question {qid} missing explanation.")

        if not question.get("sourceTags") and not question.get("sourceType"):
            warnings.append(f"Question {qid} missing source.")

        if not question.get("status"):
            warnings.append(f"Question {qid} missing status.")

        if not question.get("lineage"):
            warnings.append(f"Question {qid} missing lineage.")

        if question.get("status") == "generated":
            stem = str(question.get("question") or "").lower()
            answer = question.get("answer")
            exact_answers = answer if isinstance(answer, list) else [answer]
            for value in exact_answers:
                text = str(value or "").strip().lower()
                if text and len(text) > 6 and text in stem:
                    warnings.append(f"Question {qid} generated stem includes exact answer phrase.")
                    break

    for duplicate in sorted(duplicates):
        warnings.append(f'Duplicate question ID "{duplicate}".')

    return warnings


def validate_db_question(question) -> list[str]:
    return validate_course_pack(
        {
            "questions": [
                {
                    "id": question.legacy_id or str(question.id),
                    "type": question.question_type,
                    "topic": question.topic,
                    "difficulty": question.difficulty,
                    "probability": question.oa_probability,
                    "question": question.question_text,
                    "choices": question.choices_json,
                    "answer": question.answer_json,
                    "explanation": question.explanation,
                    "sourceTags": (question.lineage_json or {}).get("sourceTags"),
                    "status": question.status,
                    "confidence": question.confidence,
                    "lineage": question.lineage_json,
                }
            ]
        }
    )
