import { apiGet } from "./api.js";

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Unable to load ${path}: ${response.status}`);
  }
  return response.json();
}

async function fetchOptionalJson(path, fallback) {
  try {
    return await fetchJson(path);
  } catch (error) {
    console.warn(error.message);
    return fallback;
  }
}

function normalizeApiCourse(course) {
  return {
    id: course.course_code,
    name: course.name,
    shortName: course.short_name || course.shortName || course.course_code,
    description: course.description,
    path: `data/${course.course_code}/`,
    backendId: course.id,
    provider: course.provider,
    examType: course.exam_type
  };
}

export async function loadCourses(options = {}) {
  if (options.backend) {
    const courses = await apiGet("/api/courses");
    return courses.map(normalizeApiCourse);
  }
  return fetchJson("data/courses.json");
}

export async function loadCourseBundle(course, options = {}) {
  if (options.backend) {
    const exported = await apiGet(`/api/export/${encodeURIComponent(course.id)}`);
    return {
      course,
      meta: exported.course || exported.meta,
      questions: exported.questions || [],
      flashcards: exported.flashcards || [],
      glossary: exported.glossary || [],
      cheatsheets: exported.cheatsheets || [],
      mockExams: exported.mockExams || [],
      sources: exported.sources || []
    };
  }

  const basePath = course.path.endsWith("/") ? course.path : `${course.path}/`;
  const [meta, questions, flashcards, glossary, cheatsheets, mockExams, sources] = await Promise.all([
    fetchJson(`${basePath}course.json`),
    fetchJson(`${basePath}questions.json`),
    fetchOptionalJson(`${basePath}flashcards.json`, []),
    fetchOptionalJson(`${basePath}glossary.json`, []),
    fetchOptionalJson(`${basePath}cheatsheets.json`, []),
    fetchOptionalJson(`${basePath}mock-exams.json`, []),
    fetchOptionalJson(`${basePath}sources.json`, [])
  ]);

  return {
    course,
    meta,
    questions,
    flashcards,
    glossary,
    cheatsheets,
    mockExams,
    sources
  };
}
