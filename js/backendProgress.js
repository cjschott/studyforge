import { apiDelete, apiGet, apiPost, isBackendMode } from "./api.js";

function runSync(label, callback) {
  if (!isBackendMode()) return;
  callback().catch((error) => {
    console.warn(`StudyForge backend sync failed for ${label}: ${error.message}`);
    document.dispatchEvent(new CustomEvent("studyforge:sync-warning", {
      detail: { label, message: error.message }
    }));
  });
}

export async function loadBackendCourseState(courseId) {
  if (!isBackendMode()) return null;
  return apiGet(`/api/courses/${encodeURIComponent(courseId)}/progress`);
}

export function syncQuestionAttempt(courseId, question, selected, isCorrect, options = {}) {
  runSync("question attempt", () => apiPost(`/api/questions/${encodeURIComponent(question.id)}/attempt`, {
    selected_answer: selected,
    is_correct: Boolean(isCorrect),
    mode: options.source || "practice",
    time_spent_seconds: options.timeSpentSeconds || null
  }));
}

export function syncBookmark(question, enabled) {
  runSync("bookmark", () => {
    const path = `/api/questions/${encodeURIComponent(question.id)}/bookmark`;
    return enabled ? apiPost(path, {}) : apiDelete(path);
  });
}

export function syncMockExam(courseId, result) {
  runSync("mock exam", () => apiPost(`/api/courses/${encodeURIComponent(courseId)}/mock-sessions`, {
    scorePct: result.scorePct,
    questionCount: result.questionCount || result.total,
    passEstimate: result.passEstimate,
    topicBreakdown: result.topicBreakdown || [],
    review: result.review || []
  }));
}

export function syncReviewNote(question, note) {
  runSync("review note", () => apiPost(`/api/questions/${encodeURIComponent(question.id)}/review-note`, {
    note
  }));
}
