import { loadCourseBundle, loadCourses } from "./courses.js";
import { calculateMetrics } from "./analytics.js";
import { APP_CONFIG } from "./config.js";
import { apiState, detectBackend, isBackendMode } from "./api.js";
import { fetchCurrentUser, login, logout, renderLoginView } from "./authClient.js";
import { loadBackendCourseState } from "./backendProgress.js";
import { renderAdmin, renderAnalytics, renderCourseBuilder, renderDashboard, renderSettings, renderStudyGuide } from "./dashboard.js";
import { renderFlashcards } from "./flashcards.js";
import { renderMockExam } from "./mockExam.js";
import { renderQuestionMode } from "./practice.js";
import { renderSearch } from "./search.js";
import { ensureCourseState, getCourseState, getSettings, replaceCourseState, resetCourseProgress, updateSettings } from "./storage.js";
import { validateCourseBundle } from "./validation.js";

const root = document.querySelector("#main-view");
const courseSelect = document.querySelector("#course-select");
const navButtons = Array.from(document.querySelectorAll("[data-view]"));
const topbarCourse = document.querySelector("#topbar-course");
const topbarTotal = document.querySelector("#topbar-total");
const topbarAccuracy = document.querySelector("#topbar-accuracy");
const topbarMode = document.querySelector("#topbar-mode");
const resetCourseButton = document.querySelector("#reset-course");
const statusRegion = document.querySelector("#status-region");
const appVersion = document.querySelector("#app-version");
const backendStatus = document.querySelector("#backend-status");
const userArea = document.querySelector("#user-area");
const adminNav = document.querySelector("[data-view='admin']");

const viewLabels = {
  dashboard: "Dashboard",
  studyGuide: "Study Guide",
  study: "Study Mode",
  practice: "Practice",
  mock: "Mock OA",
  flashcards: "Flashcards",
  review: "Review Missed",
  bookmarks: "Bookmarks",
  search: "Search",
  analytics: "Analytics",
  courseBuilder: "Course Builder",
  admin: "Administration",
  settings: "Settings"
};

const app = {
  courses: [],
  course: null,
  bundle: null,
  view: "dashboard",
  params: {},
  cleanupCallbacks: [],
  mockExam: null,
  user: null
};

function showStatus(message) {
  statusRegion.innerHTML = `<div class="toast">${message}</div>`;
  window.setTimeout(() => {
    statusRegion.innerHTML = "";
  }, 3200);
}

function runCleanup() {
  app.cleanupCallbacks.forEach((callback) => callback());
  app.cleanupCallbacks = [];
}

function onCleanup(callback) {
  app.cleanupCallbacks.push(callback);
}

function context() {
  return {
    app,
    bundle: app.bundle,
    params: app.params,
    root,
    navigate,
    rerender: render,
    updateChrome,
    showStatus,
    onCleanup
  };
}

function navigate(view, params = {}) {
  app.view = view;
  app.params = params;
  render();
}

function setActiveNav() {
  const activeView = app.view === "study" ? "studyGuide" : app.view;
  navButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.view === activeView);
  });
}

function updateChrome() {
  if (!app.bundle) return;
  const courseState = getCourseState(app.bundle.meta.id);
  const metrics = calculateMetrics(app.bundle, courseState);
  topbarCourse.textContent = app.bundle.meta.name;
  topbarTotal.textContent = String(metrics.totalQuestions);
  topbarAccuracy.textContent = `${metrics.accuracy}%`;
  topbarMode.textContent = viewLabels[app.view] || "Study";
}

function updateBackendChrome() {
  const backend = apiState();
  backendStatus.classList.toggle("api", backend.available && backend.authenticated);
  backendStatus.classList.toggle("local", !backend.available || !backend.authenticated);
  backendStatus.textContent = backend.available
    ? backend.authenticated ? "Backend Mode" : "Backend Login"
    : "Local Mode";

  if (app.user) {
    userArea.hidden = false;
    userArea.innerHTML = `
      <span>${app.user.display_name || app.user.username}</span>
      <small>${app.user.role}</small>
      <button id="logout-button" class="button" type="button">Logout</button>
    `;
    userArea.querySelector("#logout-button").addEventListener("click", async () => {
      await logout();
      app.user = null;
      window.location.reload();
    });
  } else {
    userArea.hidden = true;
    userArea.innerHTML = "";
  }

  if (adminNav) {
    adminNav.hidden = app.user?.role !== "admin";
  }
}

function renderError(error) {
  root.innerHTML = `
    <section class="empty-state">
      <h2>StudyForge could not load.</h2>
      <p>${error.message}</p>
      <p class="muted">Check that the JSON files exist and the app is served over HTTP by nginx or another static server.</p>
    </section>
  `;
}

function render() {
  runCleanup();
  if (!app.bundle) return;
  document.body.classList.toggle("compact", getSettings().compactMode);
  setActiveNav();
  updateChrome();
  root.focus({ preventScroll: true });

  const ctx = context();
  if (app.view === "dashboard") renderDashboard(ctx);
  if (app.view === "studyGuide") renderStudyGuide(ctx);
  if (app.view === "study") renderQuestionMode(ctx, "study");
  if (app.view === "practice") renderQuestionMode(ctx, "practice");
  if (app.view === "mock") renderMockExam(ctx);
  if (app.view === "flashcards") renderFlashcards(ctx);
  if (app.view === "review") renderQuestionMode(ctx, "review");
  if (app.view === "bookmarks") renderQuestionMode(ctx, "bookmarks");
  if (app.view === "search") renderSearch(ctx);
  if (app.view === "analytics") renderAnalytics(ctx);
  if (app.view === "courseBuilder") renderCourseBuilder(ctx);
  if (app.view === "admin") renderAdmin(ctx);
  if (app.view === "settings") renderSettings(ctx);
}

async function setCourse(courseId) {
  const course = app.courses.find((item) => item.id === courseId) || app.courses[0];
  if (!course) throw new Error("No courses are defined in data/courses.json.");
  app.course = course;
  app.bundle = await loadCourseBundle(course, { backend: isBackendMode() });
  validateCourseBundle(app.bundle);
  app.mockExam = null;
  ensureCourseState(course.id);
  if (isBackendMode()) {
    const backendState = await loadBackendCourseState(course.id);
    if (backendState) replaceCourseState(course.id, backendState);
  }
  courseSelect.value = course.id;
  render();
}

async function loadApplicationData() {
  app.courses = await loadCourses({ backend: isBackendMode() });
  courseSelect.innerHTML = app.courses.map((course) => `
    <option value="${course.id}">${course.shortName || course.name}</option>
  `).join("");

  const settings = getSettings();
  const defaultCourse = settings.defaultCourse || app.courses[0]?.id;
  await setCourse(defaultCourse);
}

function setupEvents() {
  appVersion.textContent = APP_CONFIG.displayVersion;

  navButtons.forEach((button) => {
    button.addEventListener("click", () => {
      navigate(button.dataset.view);
    });
  });

  courseSelect.addEventListener("change", async () => {
    updateSettings({ defaultCourse: courseSelect.value });
    await setCourse(courseSelect.value);
    showStatus("Course loaded.");
  });

  resetCourseButton.addEventListener("click", () => {
    if (!app.bundle) return;
    if (confirm(`Reset progress for ${app.bundle.meta.shortName || app.bundle.meta.name}?`)) {
      resetCourseProgress(app.bundle.meta.id);
      app.mockExam = null;
      showStatus("Course progress reset.");
      render();
    }
  });
}

async function init() {
  try {
    setupEvents();
    await detectBackend();
    if (apiState().available) {
      try {
        app.user = await fetchCurrentUser();
      } catch (error) {
        updateBackendChrome();
        renderLoginView(root, async (username, password) => {
          app.user = await login(username, password);
          updateBackendChrome();
          await loadApplicationData();
        });
        return;
      }
    }
    updateBackendChrome();
    await loadApplicationData();
  } catch (error) {
    console.error(error);
    renderError(error);
  }
}

init();
