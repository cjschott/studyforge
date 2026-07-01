const REQUIRED_QUESTION_FIELDS = [
  "id",
  "topic",
  "difficulty",
  "probability",
  "question",
  "choices",
  "answer",
  "explanation"
];

function questionType(question) {
  return question.type || question.questionType || "single_choice";
}

function numericInRange(value, min, max) {
  return Number.isInteger(value) && value >= min && value <= max;
}

function warn(message, detail) {
  if (detail === undefined) {
    console.warn(`[StudyForge data] ${message}`);
    return;
  }
  console.warn(`[StudyForge data] ${message}`, detail);
}

export function validateCourseBundle(bundle) {
  const warnings = [];
  const questions = Array.isArray(bundle.questions) ? bundle.questions : [];
  const topics = Array.isArray(bundle.meta?.topics) ? bundle.meta.topics : [];
  const ids = new Set();
  const duplicateIds = new Set();

  questions.forEach((question, index) => {
    REQUIRED_QUESTION_FIELDS.forEach((field) => {
      if (question[field] === undefined || question[field] === null || question[field] === "") {
        warnings.push(`Question ${index + 1} is missing required field "${field}".`);
      }
    });

    if (question.id) {
      if (ids.has(question.id)) duplicateIds.add(question.id);
      ids.add(question.id);
    }

    const type = questionType(question);
    if (["single_choice", "diagram"].includes(type)) {
      if (!Array.isArray(question.choices) || question.choices.length < 2) {
        warnings.push(`Question ${question.id || index + 1} should have at least two choices.`);
      } else if (!question.choices.includes(question.answer)) {
        warnings.push(`Question ${question.id || index + 1} answer is not present in choices.`);
      }
    }

    if (type === "multi_select") {
      if (!Array.isArray(question.answer)) {
        warnings.push(`Question ${question.id || index + 1} multi_select answer must be an array.`);
      } else if (!Array.isArray(question.choices) || question.answer.some((answer) => !question.choices.includes(answer))) {
        warnings.push(`Question ${question.id || index + 1} multi_select answer contains values not present in choices.`);
      }
    }

    if (type === "matching") {
      const choicesValid = question.choices
        && Array.isArray(question.choices.left)
        && Array.isArray(question.choices.right);
      if (!choicesValid || !question.answer || typeof question.answer !== "object" || Array.isArray(question.answer)) {
        warnings.push(`Question ${question.id || index + 1} matching question is malformed.`);
      }
    }

    if (type === "ordering" && (!Array.isArray(question.choices) || !Array.isArray(question.answer))) {
      warnings.push(`Question ${question.id || index + 1} ordering question is malformed.`);
    }

    const probability = Number(question.probability);
    if (!Number.isFinite(probability) || probability < 1 || probability > 5) {
      warnings.push(`Question ${question.id || index + 1} probability should be between 1 and 5.`);
    }

    if (typeof question.difficulty === "number" && !numericInRange(question.difficulty, 1, 5)) {
      warnings.push(`Question ${question.id || index + 1} difficulty should be between 1 and 5.`);
    }

    if (question.confidence !== undefined && !numericInRange(question.confidence, 1, 10)) {
      warnings.push(`Question ${question.id || index + 1} confidence should be between 1 and 10.`);
    }

    if (!question.explanation) {
      warnings.push(`Question ${question.id || index + 1} missing explanation.`);
    }

    if (!question.sourceTags?.length && !question.sourceType) {
      warnings.push(`Question ${question.id || index + 1} missing source.`);
    }

    if (!question.status) {
      warnings.push(`Question ${question.id || index + 1} missing status.`);
    }

    if (!question.lineage) {
      warnings.push(`Question ${question.id || index + 1} missing lineage.`);
    }

    if (question.topic && topics.length && !topics.includes(question.topic)) {
      warnings.push(`Question ${question.id || index + 1} uses topic "${question.topic}" not listed in course.json.`);
    }
  });

  topics.forEach((topic) => {
    const hasTopicContent = questions.some((question) => question.topic === topic)
      || (bundle.flashcards || []).some((card) => card.topic === topic)
      || (bundle.glossary || []).some((term) => term.topic === topic)
      || (bundle.cheatsheets || []).some((sheet) => sheet.topic === topic);

    if (!hasTopicContent) {
      warnings.push(`Topic "${topic}" has no course-pack content.`);
    }
  });

  duplicateIds.forEach((id) => warnings.push(`Duplicate question ID "${id}".`));

  if (warnings.length) {
    console.groupCollapsed(`StudyForge course validation: ${warnings.length} warning(s) for ${bundle.meta?.shortName || bundle.meta?.id || "course"}`);
    warnings.forEach((message) => warn(message));
    console.groupEnd();
  } else {
    console.info(`StudyForge course validation passed for ${bundle.meta?.shortName || bundle.meta?.id || "course"}.`);
  }

  return warnings;
}
