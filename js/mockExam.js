import { recordMockExam } from "./storage.js";
import { collectAnswer, formatAnswer, hasAnswer, questionType, renderQuestionControl, renderQuestionMedia, scoreQuestion } from "./questionTypes.js";

function shuffle(items) {
  return items
    .map((item) => ({ item, sort: Math.random() }))
    .sort((a, b) => a.sort - b.sort)
    .map(({ item }) => item);
}

function selectMockQuestions(questions, count) {
  const highProbability = shuffle(questions.filter((question) => Number(question.probability || 0) >= 4));
  const remaining = shuffle(questions.filter((question) => Number(question.probability || 0) < 4));
  return [...highProbability, ...remaining].slice(0, Math.min(count, questions.length));
}

function remainingText(exam) {
  if (!exam.timerEnabled) return "Untimed";
  const elapsedMs = Date.now() - exam.startedAt;
  const totalMs = exam.durationMinutes * 60 * 1000;
  const remainingMs = Math.max(0, totalMs - elapsedMs);
  const minutes = Math.floor(remainingMs / 60000);
  const seconds = Math.floor((remainingMs % 60000) / 1000);
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function buildResult(bundle, exam) {
  const questionsById = new Map(bundle.questions.map((question) => [question.id, question]));
  const review = exam.questionIds.map((id) => {
    const question = questionsById.get(id);
    const selected = exam.answers[id] || "";
    const correct = scoreQuestion(question, selected);
    return {
      id,
      topic: question.topic,
      question: question.question,
      selected,
      answer: question.answer,
      explanation: question.explanation,
      correct
    };
  });
  const correct = review.filter((item) => item.correct).length;
  const topicMap = {};

  review.forEach((item) => {
    if (!topicMap[item.topic]) {
      topicMap[item.topic] = { topic: item.topic, total: 0, correct: 0 };
    }
    topicMap[item.topic].total += 1;
    if (item.correct) topicMap[item.topic].correct += 1;
  });

  return {
    id: `mock-${Date.now()}`,
    total: review.length,
    correct,
    scorePct: review.length ? Math.round((correct / review.length) * 100) : 0,
    passEstimate: review.length && Math.round((correct / review.length) * 100) >= 70 ? "Pass range" : "Needs review",
    questionCount: review.length,
    durationMinutes: Math.max(1, Math.round((Date.now() - exam.startedAt) / 60000)),
    topicBreakdown: Object.values(topicMap)
      .map((topic) => ({
        ...topic,
        scorePct: Math.round((topic.correct / topic.total) * 100)
      }))
      .sort((a, b) => a.scorePct - b.scorePct || b.total - a.total),
    review
  };
}

function submitExam(ctx, exam, reason = "Mock OA saved") {
  const result = buildResult(ctx.bundle, exam);
  recordMockExam(ctx.bundle.meta.id, result);
  ctx.app.mockExam = { active: false, result };
  ctx.showStatus(`${reason}: ${result.scorePct}%.`);
  ctx.updateChrome();
  ctx.rerender();
}

function renderStart(ctx) {
  const previousResult = ctx.app.mockExam?.result;
  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Mock OA</h2>
        <p class="muted">Timed exam mode. Answers are hidden until the exam is submitted.</p>
      </div>
    </div>

    <section class="grid grid-2">
      <article class="card">
        <h3>Start Mock Exam</h3>
        <form id="mock-start" class="grid">
          <div class="field">
            <label for="mock-count">Question count</label>
            <select id="mock-count" class="course-select" name="count">
              <option value="25">25 questions</option>
              <option value="50">50 questions</option>
              <option value="75" selected>75 questions</option>
              <option value="100">100 questions</option>
            </select>
          </div>
          <label class="toggle-row">
            <span>Use timer</span>
            <input id="mock-timer-enabled" name="timerEnabled" type="checkbox" checked>
          </label>
          <div class="field">
            <label for="mock-duration">Timer minutes</label>
            <input id="mock-duration" class="input" name="duration" type="number" min="10" max="240" value="120">
          </div>
          <button class="button button-primary" type="submit">Start Mock OA</button>
        </form>
      </article>
      <article class="card">
        <h3>Selection Rules</h3>
        <p>Mock exams pull from high-probability questions first, then fill remaining slots randomly.</p>
        <p class="muted">Use flags for questions you want to inspect before final submit.</p>
      </article>
    </section>

    ${previousResult ? `
      <section class="card" style="margin-top: 1rem;">
        <h3>Latest Review</h3>
        <p>Score: ${previousResult.scorePct}% (${previousResult.correct}/${previousResult.total}) - ${previousResult.passEstimate}</p>
      </section>
    ` : `
      <section class="empty-state" style="margin-top: 1rem;">
        <h2>No active mock exam.</h2>
        <p>Start a timed Mock OA when you are ready to test without seeing answers until the end.</p>
      </section>
    `}
  `;

  ctx.root.querySelector("#mock-start").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!confirm("Start a new Mock OA? This will replace any in-progress mock exam in this browser.")) return;
    const data = new FormData(event.currentTarget);
    const selected = selectMockQuestions(ctx.bundle.questions, Number(data.get("count")));
    ctx.app.mockExam = {
      active: true,
      reviewing: false,
      questionIds: selected.map((question) => question.id),
      index: 0,
      answers: {},
      flags: {},
      startedAt: Date.now(),
      timerEnabled: data.get("timerEnabled") === "on",
      durationMinutes: Number(data.get("duration") || 120)
    };
    ctx.rerender();
  });
}

function renderActive(ctx, exam) {
  const questionsById = new Map(ctx.bundle.questions.map((question) => [question.id, question]));
  const currentId = exam.questionIds[exam.index];
  const question = questionsById.get(currentId);
  const answer = exam.answers[currentId] || "";
  const flagged = Boolean(exam.flags[currentId]);
  const answeredCount = Object.keys(exam.answers).length;

  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Mock OA</h2>
        <p class="muted">Question ${exam.index + 1} of ${exam.questionIds.length} - ${answeredCount} answered</p>
      </div>
      <div class="button-row">
        <span id="mock-timer" class="tag yellow">${remainingText(exam)}</span>
        <button id="finish-mock" class="button button-danger" type="button">Finish</button>
      </div>
    </div>

    <section class="mock-layout">
      <article class="card question-card">
        <div class="button-row">
          <span class="tag blue">${question.topic}</span>
          <span class="tag">${question.subtopic || "General"}</span>
          <span class="tag yellow">Probability ${question.probability}</span>
          <span class="tag">${questionType(question)}</span>
        </div>
        <p class="question-text">${question.question}</p>
        ${renderQuestionMedia(question)}
        ${renderQuestionControl(question, "mock-choice", answer)}
        <div class="button-row">
          <button id="mock-prev" class="button" type="button" ${exam.index === 0 ? "disabled" : ""}>Previous</button>
          <button id="mock-next" class="button" type="button" ${exam.index === exam.questionIds.length - 1 ? "disabled" : ""}>Next</button>
          <button id="mock-flag" class="button ${flagged ? "button-warning" : ""}" type="button">${flagged ? "Flagged" : "Flag"}</button>
        </div>
      </article>

      <aside class="card">
        <h3>Questions</h3>
        <div class="question-palette">
          ${exam.questionIds.map((id, index) => `
            <button class="palette-button ${index === exam.index ? "current" : ""} ${exam.answers[id] ? "answered" : ""} ${exam.flags[id] ? "flagged" : ""}" data-index="${index}" type="button">${index + 1}</button>
          `).join("")}
        </div>
      </aside>
    </section>
  `;

  ctx.root.querySelectorAll("[data-question-input]").forEach((input) => {
    const eventName = input.tagName === "TEXTAREA" ? "input" : "change";
    input.addEventListener(eventName, () => {
      const selected = collectAnswer(ctx.root, question, "mock-choice");
      if (hasAnswer(question, selected)) {
        exam.answers[currentId] = selected;
      } else {
        delete exam.answers[currentId];
      }
      ctx.rerender();
    });
  });
  ctx.root.querySelector("#mock-prev").addEventListener("click", () => {
    exam.index = Math.max(0, exam.index - 1);
    ctx.rerender();
  });
  ctx.root.querySelector("#mock-next").addEventListener("click", () => {
    exam.index = Math.min(exam.questionIds.length - 1, exam.index + 1);
    ctx.rerender();
  });
  ctx.root.querySelector("#mock-flag").addEventListener("click", () => {
    exam.flags[currentId] = !exam.flags[currentId];
    ctx.rerender();
  });
  ctx.root.querySelector("#finish-mock").addEventListener("click", () => {
    if (!confirm("Review flagged and unanswered questions before final submit?")) return;
    exam.reviewing = true;
    ctx.rerender();
  });
  ctx.root.querySelectorAll(".palette-button").forEach((button) => {
    button.addEventListener("click", () => {
      exam.index = Number(button.dataset.index);
      ctx.rerender();
    });
  });

  if (exam.timerEnabled) {
    const timerId = window.setInterval(() => {
      const timer = document.querySelector("#mock-timer");
      if (timer) timer.textContent = remainingText(exam);
      const elapsedMs = Date.now() - exam.startedAt;
      if (elapsedMs >= exam.durationMinutes * 60 * 1000) {
        window.clearInterval(timerId);
        submitExam(ctx, exam, "Time expired. Mock OA saved");
      }
    }, 1000);
    ctx.onCleanup(() => window.clearInterval(timerId));
  }
}

function renderReviewBeforeSubmit(ctx, exam) {
  const questionsById = new Map(ctx.bundle.questions.map((question) => [question.id, question]));
  const flagged = exam.questionIds.filter((id) => exam.flags[id]);
  const unanswered = exam.questionIds.filter((id) => !exam.answers[id]);

  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Final Mock Review</h2>
        <p class="muted">Answers are still hidden. Review flags and blanks before final scoring.</p>
      </div>
      <div class="button-row">
        <button id="back-to-mock" class="button" type="button">Back To Exam</button>
        <button id="submit-mock-final" class="button button-danger" type="button">Submit Final</button>
      </div>
    </div>

    <section class="grid grid-2">
      <article class="card">
        <h3>Flagged Questions</h3>
        ${flagged.length ? `
          <div class="grid">
            ${flagged.map((id) => {
              const question = questionsById.get(id);
              const index = exam.questionIds.indexOf(id);
              return `<button class="search-result" type="button" data-jump="${index}"><span class="tag yellow">Flagged</span><h3>Question ${index + 1}</h3><p class="muted">${question.question}</p></button>`;
            }).join("")}
          </div>
        ` : `<p class="muted">No flagged questions.</p>`}
      </article>
      <article class="card">
        <h3>Unanswered Questions</h3>
        ${unanswered.length ? `
          <div class="grid">
            ${unanswered.map((id) => {
              const question = questionsById.get(id);
              const index = exam.questionIds.indexOf(id);
              return `<button class="search-result" type="button" data-jump="${index}"><span class="tag red">Unanswered</span><h3>Question ${index + 1}</h3><p class="muted">${question.question}</p></button>`;
            }).join("")}
          </div>
        ` : `<p class="muted">No unanswered questions.</p>`}
      </article>
    </section>
  `;

  ctx.root.querySelector("#back-to-mock").addEventListener("click", () => {
    exam.reviewing = false;
    ctx.rerender();
  });
  ctx.root.querySelector("#submit-mock-final").addEventListener("click", () => {
    const warning = unanswered.length ? `${unanswered.length} questions are unanswered. ` : "";
    if (!confirm(`${warning}Submit this Mock OA for final scoring?`)) return;
    submitExam(ctx, exam);
  });
  ctx.root.querySelectorAll("[data-jump]").forEach((button) => {
    button.addEventListener("click", () => {
      exam.index = Number(button.dataset.jump);
      exam.reviewing = false;
      ctx.rerender();
    });
  });
}

function renderResult(ctx, result) {
  const weakTopics = result.topicBreakdown
    .filter((topic) => topic.scorePct < 80)
    .sort((a, b) => a.scorePct - b.scorePct);
  const missed = result.review.filter((item) => !item.correct);

  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Mock OA Results</h2>
        <p class="muted">Final score ${result.scorePct}% - ${result.correct}/${result.total} correct</p>
      </div>
      <button id="new-mock" class="button button-primary" type="button">Start New Mock</button>
    </div>

    <section class="grid grid-4">
      <article class="card"><span class="stat-value">${result.scorePct}%</span><span class="stat-label">Total score</span></article>
      <article class="card"><span class="stat-value">${result.passEstimate}</span><span class="stat-label">70% threshold estimate</span></article>
      <article class="card"><span class="stat-value">${result.correct}</span><span class="stat-label">Correct answers</span></article>
      <article class="card"><span class="stat-value">${result.durationMinutes}</span><span class="stat-label">Minutes used</span></article>
    </section>

    <section class="grid grid-2" style="margin-top: 1rem;">
      <article class="card">
        <h3>Topic Breakdown</h3>
        <table class="data-table">
          <thead><tr><th>Topic</th><th>Score</th><th>Correct</th></tr></thead>
          <tbody>
            ${result.topicBreakdown.map((topic) => `<tr><td>${topic.topic}</td><td>${topic.scorePct}%</td><td>${topic.correct}/${topic.total}</td></tr>`).join("")}
          </tbody>
        </table>
      </article>
      <article class="card">
        <h3>Recommended Next Topics</h3>
        ${weakTopics.length ? `<ul class="pill-list">${weakTopics.map((topic) => `<li class="tag yellow">Review ${topic.topic}</li>`).join("")}</ul>` : `<p class="muted">No topic scored below 80%.</p>`}
      </article>
    </section>

    <div class="section-title"><h3>Missed Question Review</h3><span class="muted">${missed.length} missed</span></div>
    <section class="grid">
      ${missed.length ? missed.map((item, index) => `
        <article class="card">
          <div class="button-row">
            <span class="tag red">Missed</span>
            <span class="tag blue">${item.topic}</span>
            <span class="tag">Missed ${index + 1}</span>
          </div>
          <p class="question-text">${item.question}</p>
          <p><strong>Your answer:</strong> ${item.selected ? formatAnswer(item.selected) : "No answer"}</p>
          <p><strong>Correct answer:</strong> ${formatAnswer(item.answer)}</p>
          <p class="muted">${item.explanation}</p>
        </article>
      `).join("") : `
        <article class="empty-state">
          <h2>No missed questions.</h2>
          <p>Every answered item on this mock exam was correct.</p>
        </article>
      `}
    </section>
  `;

  ctx.root.querySelector("#new-mock").addEventListener("click", () => {
    if (!confirm("Start a new Mock OA and clear this on-screen result? The saved history will remain in Analytics.")) return;
    ctx.app.mockExam = null;
    ctx.rerender();
  });
}

export function renderMockExam(ctx) {
  if (ctx.app.mockExam?.active && ctx.app.mockExam?.reviewing) {
    renderReviewBeforeSubmit(ctx, ctx.app.mockExam);
    return;
  }
  if (ctx.app.mockExam?.active) {
    renderActive(ctx, ctx.app.mockExam);
    return;
  }
  if (ctx.app.mockExam?.result) {
    renderResult(ctx, ctx.app.mockExam.result);
    return;
  }
  renderStart(ctx);
}
