import { APP_CONFIG } from "./config.js";
import { syncBookmark, syncMockExam, syncQuestionAttempt, syncReviewNote } from "./backendProgress.js";

const STORAGE_KEY = APP_CONFIG.storageKey;

const DEFAULT_SETTINGS = {
  compactMode: false,
  showMemoryDefault: true,
  autoNext: false,
  defaultCourse: ""
};

function defaultCourseState() {
  return {
    answered: {},
    missed: {},
    bookmarks: {},
    reviewLater: {},
    missedNotes: {},
    topicStats: {},
    sessions: [],
    mockExams: [],
    flashcards: {}
  };
}

function normalizeState(state) {
  const base = {
    version: 1,
    settings: { ...DEFAULT_SETTINGS },
    courses: {}
  };

  if (!state || typeof state !== "object") {
    return base;
  }

  return {
    version: 1,
    settings: { ...DEFAULT_SETTINGS, ...(state.settings || {}) },
    courses: state.courses && typeof state.courses === "object" ? state.courses : {}
  };
}

function readState() {
  try {
    return normalizeState(JSON.parse(localStorage.getItem(STORAGE_KEY)));
  } catch (error) {
    console.warn("StudyForge progress could not be parsed. Starting clean.", error);
    return normalizeState();
  }
}

function writeState(state) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizeState(state)));
}

function ensureCourseStateIn(state, courseId) {
  if (!state.courses[courseId]) {
    state.courses[courseId] = defaultCourseState();
  }

  state.courses[courseId] = {
    ...defaultCourseState(),
    ...state.courses[courseId],
    answered: state.courses[courseId].answered || {},
    missed: state.courses[courseId].missed || {},
    bookmarks: state.courses[courseId].bookmarks || {},
    reviewLater: state.courses[courseId].reviewLater || {},
    missedNotes: state.courses[courseId].missedNotes || {},
    topicStats: state.courses[courseId].topicStats || {},
    sessions: state.courses[courseId].sessions || [],
    mockExams: state.courses[courseId].mockExams || [],
    flashcards: state.courses[courseId].flashcards || {}
  };

  return state.courses[courseId];
}

function appendSession(courseState, event) {
  courseState.sessions.unshift({
    ...event,
    date: new Date().toISOString()
  });
  courseState.sessions = courseState.sessions.slice(0, 35);
}

export function getState() {
  return readState();
}

export function getSettings() {
  return readState().settings;
}

export function updateSettings(patch) {
  const state = readState();
  state.settings = { ...state.settings, ...patch };
  writeState(state);
  return state.settings;
}

export function ensureCourseState(courseId) {
  const state = readState();
  const courseState = ensureCourseStateIn(state, courseId);
  writeState(state);
  return courseState;
}

export function getCourseState(courseId) {
  const state = readState();
  const courseState = ensureCourseStateIn(state, courseId);
  return courseState;
}

export function replaceCourseState(courseId, courseState) {
  const state = readState();
  state.courses[courseId] = {
    ...defaultCourseState(),
    ...(courseState || {})
  };
  writeState(state);
  return state.courses[courseId];
}

export function resetCourseProgress(courseId) {
  const state = readState();
  state.courses[courseId] = defaultCourseState();
  writeState(state);
}

export function resetAllProgress() {
  writeState({
    version: 1,
    settings: { ...DEFAULT_SETTINGS },
    courses: {}
  });
}

export function exportProgress() {
  return JSON.stringify(readState(), null, 2);
}

export function importProgress(json) {
  const parsed = JSON.parse(json);
  const normalized = normalizeState(parsed);
  writeState(normalized);
  return normalized;
}

export function recordQuestionAnswer(courseId, question, selected, isCorrect, options = {}) {
  const state = readState();
  const courseState = ensureCourseStateIn(state, courseId);
  const scored = options.scored !== false;
  const topic = question.topic || "Uncategorized";
  const previous = courseState.answered[question.id] || {
    attempts: 0,
    correct: 0,
    missed: 0
  };

  previous.attempts += 1;
  previous.selected = selected;
  previous.topic = topic;
  previous.lastCorrect = Boolean(isCorrect);
  previous.lastAnswered = new Date().toISOString();
  previous.source = options.source || "practice";

  if (scored) {
    if (!courseState.topicStats[topic]) {
      courseState.topicStats[topic] = { answered: 0, correct: 0, missed: 0 };
    }
    courseState.topicStats[topic].answered += 1;

    if (isCorrect) {
      previous.correct += 1;
      courseState.topicStats[topic].correct += 1;
      delete courseState.missed[question.id];
    } else {
      previous.missed += 1;
      courseState.topicStats[topic].missed += 1;
      courseState.missed[question.id] = {
        id: question.id,
        topic,
        question: question.question,
        lastMissed: new Date().toISOString(),
        note: courseState.missedNotes[question.id] || ""
      };
    }

    appendSession(courseState, {
      type: options.source || "practice",
      questionId: question.id,
      topic,
      correct: Boolean(isCorrect)
    });
  }

  courseState.answered[question.id] = previous;
  writeState(state);
  syncQuestionAttempt(courseId, question, selected, isCorrect, options);
  return previous;
}

export function saveMissedNote(courseId, question, note) {
  const state = readState();
  const courseState = ensureCourseStateIn(state, courseId);
  const cleanNote = String(note || "").trim();
  courseState.missedNotes[question.id] = cleanNote;
  if (courseState.missed[question.id]) {
    courseState.missed[question.id].note = cleanNote;
  }
  writeState(state);
  syncReviewNote(question, cleanNote);
  return cleanNote;
}

export function toggleBookmark(courseId, question) {
  const state = readState();
  const courseState = ensureCourseStateIn(state, courseId);
  if (courseState.bookmarks[question.id]) {
    delete courseState.bookmarks[question.id];
  } else {
    courseState.bookmarks[question.id] = {
      id: question.id,
      topic: question.topic,
      question: question.question,
      date: new Date().toISOString()
    };
  }
  writeState(state);
  const enabled = Boolean(courseState.bookmarks[question.id]);
  syncBookmark(question, enabled);
  return enabled;
}

export function toggleReviewLater(courseId, question) {
  const state = readState();
  const courseState = ensureCourseStateIn(state, courseId);
  if (courseState.reviewLater[question.id]) {
    delete courseState.reviewLater[question.id];
  } else {
    courseState.reviewLater[question.id] = {
      id: question.id,
      topic: question.topic,
      question: question.question,
      date: new Date().toISOString()
    };
  }
  writeState(state);
  return Boolean(courseState.reviewLater[question.id]);
}

export function recordMockExam(courseId, result) {
  const state = readState();
  const courseState = ensureCourseStateIn(state, courseId);
  courseState.mockExams.unshift({
    ...result,
    date: new Date().toISOString()
  });
  courseState.mockExams = courseState.mockExams.slice(0, 20);
  appendSession(courseState, {
    type: "mock",
    scorePct: result.scorePct,
    correct: result.correct,
    total: result.total
  });
  writeState(state);
  syncMockExam(courseId, result);
}

export function recordFlashcard(courseId, card, result) {
  const state = readState();
  const courseState = ensureCourseStateIn(state, courseId);
  const current = courseState.flashcards[card.id] || {
    known: 0,
    missed: 0
  };

  if (result === "known") {
    current.known += 1;
  } else {
    current.missed += 1;
  }

  current.topic = card.topic;
  current.lastResult = result;
  current.lastReviewed = new Date().toISOString();
  courseState.flashcards[card.id] = current;
  appendSession(courseState, {
    type: "flashcard",
    cardId: card.id,
    topic: card.topic,
    result
  });
  writeState(state);
  return current;
}
