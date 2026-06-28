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

    if (!Array.isArray(question.choices) || question.choices.length < 2) {
      warnings.push(`Question ${question.id || index + 1} should have at least two choices.`);
    } else if (!question.choices.includes(question.answer)) {
      warnings.push(`Question ${question.id || index + 1} answer is not present in choices.`);
    }

    const probability = Number(question.probability);
    if (!Number.isFinite(probability) || probability < 1 || probability > 5) {
      warnings.push(`Question ${question.id || index + 1} probability should be between 1 and 5.`);
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
