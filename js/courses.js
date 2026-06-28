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

export async function loadCourses() {
  return fetchJson("data/courses.json");
}

export async function loadCourseBundle(course) {
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
