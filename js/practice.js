import { getCourseState, getSettings, recordQuestionAnswer, saveMissedNote, toggleBookmark, toggleReviewLater } from "./storage.js";

function unique(values) {
  return Array.from(new Set(values.filter(Boolean))).sort();
}

function optionList(values, selected, allLabel = "All") {
  return `<option value="">${allLabel}</option>${values.map((value) => `<option value="${value}" ${selected === value ? "selected" : ""}>${value}</option>`).join("")}`;
}

function matchesQuery(question, query) {
  if (!query) return true;
  const text = [
    question.question,
    question.topic,
    question.subtopic,
    question.difficulty,
    question.explanation,
    question.memory,
    question.examTip,
    ...(question.choices || [])
  ].join(" ").toLowerCase();
  return text.includes(query.toLowerCase());
}

function filteredQuestions(questions, params, courseState, mode) {
  let pool = questions.slice();
  if (mode === "review") {
    pool = pool.filter((question) => courseState.missed?.[question.id]);
  }
  if (mode === "bookmarks") {
    pool = pool.filter((question) => courseState.bookmarks?.[question.id] || courseState.reviewLater?.[question.id]);
  }
  if (params.topic) pool = pool.filter((question) => question.topic === params.topic);
  if (params.difficulty) pool = pool.filter((question) => question.difficulty === params.difficulty);
  if (params.probability === "5") pool = pool.filter((question) => Number(question.probability) === 5);
  if (params.probability === "4plus") pool = pool.filter((question) => Number(question.probability) >= 4);
  if (params.probability === "3minus") pool = pool.filter((question) => Number(question.probability) <= 3);
  if (params.query) pool = pool.filter((question) => matchesQuery(question, params.query));
  return pool;
}

function pickQuestion(pool, params, courseState) {
  const requested = pool.find((question) => question.id === params.questionId);
  if (requested) return requested;
  const unanswered = pool.filter((question) => !courseState.answered?.[question.id]);
  const source = unanswered.length ? unanswered : pool;
  return source[Math.floor(Math.random() * source.length)];
}

function answerPanel(question, settings, existingNote = "") {
  const sources = question.sourceTags?.length
    ? `<p><strong>Sources:</strong> ${question.sourceTags.map((tag) => `<span class="tag">${tag}</span>`).join(" ")}</p>`
    : "";

  return `
    <section id="answer-panel" class="answer-panel" hidden>
      <h4>Answer: ${question.answer}</h4>
      <p>${question.explanation}</p>
      <div class="answer-grid">
        <article>
          <h4>Memory Trick</h4>
          <p class="muted">${settings.showMemoryDefault ? question.memory || "No memory trick provided." : "Enable memory tricks in Settings or reveal this section while reviewing."}</p>
        </article>
        <article>
          <h4>Exam Tip</h4>
          <p class="muted">${question.examTip || "No exam tip provided."}</p>
        </article>
        <article>
          <h4>Source Tags</h4>
          ${sources || `<p class="muted">No source tags provided.</p>`}
        </article>
      </div>
      <div id="missed-note-panel" class="card secondary" hidden style="margin-top: 1rem;">
        <h4>Why I missed this</h4>
        <p class="helper-text">Capture the trap, clue, or memory gap while it is fresh. This note is saved locally with the question.</p>
        <textarea id="missed-note" class="textarea" placeholder="Example: confused WDM wavelengths with FDM frequency bands">${existingNote}</textarea>
        <div class="button-row" style="margin-top: 0.75rem;">
          <button id="save-missed-note" class="button button-primary" type="button">Save Note</button>
        </div>
      </div>
    </section>
  `;
}

function renderFilters(ctx, topics, difficulties) {
  return `
    <section class="card">
      <form id="question-filters" class="filter-grid">
        <div class="field">
          <label for="filter-topic">Topic</label>
          <select id="filter-topic" class="course-select" name="topic">${optionList(topics, ctx.params.topic)}</select>
        </div>
        <div class="field slim">
          <label for="filter-difficulty">Difficulty</label>
          <select id="filter-difficulty" class="course-select" name="difficulty">${optionList(difficulties, ctx.params.difficulty)}</select>
        </div>
        <div class="field slim">
          <label for="filter-probability">Probability</label>
          <select id="filter-probability" class="course-select" name="probability">
            <option value="">All</option>
            <option value="5" ${ctx.params.probability === "5" ? "selected" : ""}>5 only</option>
            <option value="4plus" ${ctx.params.probability === "4plus" ? "selected" : ""}>4+</option>
            <option value="3minus" ${ctx.params.probability === "3minus" ? "selected" : ""}>3 or less</option>
          </select>
        </div>
        <div class="field">
          <label for="filter-query">Search filter</label>
          <input id="filter-query" class="input" name="query" type="search" value="${ctx.params.query || ""}" placeholder="Term, standard, acronym">
        </div>
        <button class="button button-primary" type="submit">Apply</button>
      </form>
    </section>
  `;
}

export function renderQuestionMode(ctx, mode) {
  const courseId = ctx.bundle.meta.id;
  const courseState = getCourseState(courseId);
  const settings = getSettings();
  const topics = unique(ctx.bundle.questions.map((question) => question.topic));
  const difficulties = unique(ctx.bundle.questions.map((question) => question.difficulty));
  const pool = filteredQuestions(ctx.bundle.questions, ctx.params, courseState, mode);
  const current = pool.length ? pickQuestion(pool, ctx.params, courseState) : null;
  const title = mode === "study" ? "Study Guide Practice" : mode === "review" ? "Review Missed" : mode === "bookmarks" ? "Bookmarks" : "Practice";
  const subtitle = mode === "study"
    ? "Reveal answers freely, then score only when you choose I knew this or I missed this."
    : mode === "review"
      ? "Work through questions currently marked missed."
      : mode === "bookmarks"
        ? "Review saved and review-later questions."
        : "Answer first, then review the explanation and tips.";

  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>${title}</h2>
        <p class="muted">${subtitle}</p>
      </div>
      <span class="tag blue">${pool.length} in pool</span>
    </div>

    ${renderFilters(ctx, topics, difficulties)}

    ${current ? `
      <section class="card question-card" data-question-id="${current.id}">
        <div class="button-row">
          <span class="tag blue">${current.topic}</span>
          <span class="tag">${current.subtopic || "General"}</span>
          <span class="tag yellow">Probability ${current.probability}</span>
          <span class="tag">${current.difficulty}</span>
        </div>
        <p class="question-text">${current.question}</p>
        <div class="choice-list" role="radiogroup" aria-label="Answer choices">
          ${current.choices.map((choice, index) => `
            <label class="choice" data-choice-index="${index}">
              <input type="radio" name="answer-choice" value="${index}">
              <span>${choice}</span>
            </label>
          `).join("")}
        </div>
        <div class="button-row">
          ${mode === "practice" || mode === "review" || mode === "bookmarks" ? `<button id="submit-answer" class="button button-success" type="button">Submit</button>` : ""}
          ${mode === "study" ? `<button id="reveal-answer" class="button button-primary" type="button">Reveal Answer</button>` : ""}
          <button id="bookmark-question" class="button ${courseState.bookmarks?.[current.id] ? "button-warning" : ""}" type="button">${courseState.bookmarks?.[current.id] ? "Bookmarked" : "Bookmark"}</button>
          <button id="review-later" class="button ${courseState.reviewLater?.[current.id] ? "button-warning" : ""}" type="button">${courseState.reviewLater?.[current.id] ? "Saved for Review" : "Review Later"}</button>
          <button id="similar-question" class="button" type="button">Similar Question</button>
          <button id="next-question" class="button" type="button">Next</button>
        </div>
        ${mode === "study" ? `
          <div id="study-score-buttons" class="button-row" hidden>
            <button id="study-known" class="button button-success" type="button">I knew this</button>
            <button id="study-missed" class="button button-danger" type="button">I missed this</button>
          </div>
        ` : ""}
        ${answerPanel(current, settings, courseState.missedNotes?.[current.id] || "")}
      </section>
    ` : `
      <section class="empty-state">
        <h2>${ctx.bundle.questions.length ? `No ${title.toLowerCase()} questions match.` : "No questions loaded."}</h2>
        <p>${mode === "review" ? "Missed questions appear here after incorrect scored answers." : mode === "bookmarks" ? "Bookmarked and review-later questions appear here after you save them." : "Adjust filters, clear search terms, or add questions to this course pack."}</p>
      </section>
    `}
  `;

  ctx.root.querySelector("#question-filters").addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    ctx.navigate(ctx.app.view, {
      topic: data.get("topic"),
      difficulty: data.get("difficulty"),
      probability: data.get("probability"),
      query: String(data.get("query") || "").trim()
    });
  });

  if (!current) return;

  const correctIndex = current.choices.findIndex((choice) => choice === current.answer);
  const bookmarkButton = ctx.root.querySelector("#bookmark-question");
  const reveal = (scoreAnswer) => {
    const selectedInput = ctx.root.querySelector("input[name='answer-choice']:checked");
    const selectedIndex = selectedInput ? Number(selectedInput.value) : -1;
    const selected = selectedIndex >= 0 ? current.choices[selectedIndex] : "";
    const isCorrect = selectedIndex === correctIndex;

    ctx.root.querySelectorAll(".choice").forEach((choiceEl) => {
      const index = Number(choiceEl.dataset.choiceIndex);
      choiceEl.classList.toggle("selected", index === selectedIndex);
      choiceEl.classList.toggle("correct", index === correctIndex);
      choiceEl.classList.toggle("wrong", selectedIndex >= 0 && index === selectedIndex && index !== correctIndex);
      choiceEl.querySelector("input").disabled = true;
    });

    ctx.root.querySelector("#answer-panel").hidden = false;
    const submit = ctx.root.querySelector("#submit-answer");
    if (submit) submit.disabled = true;
    const studyButtons = ctx.root.querySelector("#study-score-buttons");
    if (studyButtons) studyButtons.hidden = false;

    if (scoreAnswer) {
      recordQuestionAnswer(courseId, current, selected, isCorrect, { source: mode });
      ctx.updateChrome();
      const missedNotePanel = ctx.root.querySelector("#missed-note-panel");
      if (!isCorrect && missedNotePanel) missedNotePanel.hidden = false;
      if (settings.autoNext && isCorrect && mode === "practice") {
        window.setTimeout(() => nextQuestion(), 700);
      }
    }
  };

  const nextQuestion = () => {
    const nextPool = pool.filter((question) => question.id !== current.id);
    const next = nextPool.length ? nextPool[Math.floor(Math.random() * nextPool.length)] : current;
    ctx.navigate(ctx.app.view, { ...ctx.params, questionId: next.id });
  };

  const similarQuestion = () => {
    const sameSubtopic = pool.filter((question) => question.id !== current.id && question.topic === current.topic && question.subtopic === current.subtopic);
    const sameTopic = pool.filter((question) => question.id !== current.id && question.topic === current.topic);
    const candidates = sameSubtopic.length ? sameSubtopic : sameTopic;
    if (!candidates.length) {
      ctx.showStatus("No similar question found in the current pool.");
      return;
    }
    const next = candidates[Math.floor(Math.random() * candidates.length)];
    ctx.navigate(ctx.app.view, { ...ctx.params, questionId: next.id });
  };

  const selectChoice = (index) => {
    const input = ctx.root.querySelector(`input[name='answer-choice'][value='${index}']`);
    if (!input || input.disabled) return;
    input.checked = true;
    ctx.root.querySelectorAll(".choice").forEach((choice) => choice.classList.remove("selected"));
    input.closest(".choice").classList.add("selected");
  };

  ctx.root.querySelectorAll("input[name='answer-choice']").forEach((input) => {
    input.addEventListener("change", () => {
      ctx.root.querySelectorAll(".choice").forEach((choice) => choice.classList.remove("selected"));
      input.closest(".choice").classList.add("selected");
    });
  });

  ctx.root.querySelector("#submit-answer")?.addEventListener("click", () => {
    if (!ctx.root.querySelector("input[name='answer-choice']:checked")) {
      ctx.showStatus("Choose an answer first.");
      return;
    }
    reveal(true);
  });

  ctx.root.querySelector("#reveal-answer")?.addEventListener("click", () => reveal(false));
  ctx.root.querySelector("#next-question").addEventListener("click", nextQuestion);
  bookmarkButton.addEventListener("click", () => {
    toggleBookmark(courseId, current);
    ctx.rerender();
  });
  ctx.root.querySelector("#review-later").addEventListener("click", () => {
    toggleReviewLater(courseId, current);
    ctx.rerender();
  });
  ctx.root.querySelector("#similar-question").addEventListener("click", similarQuestion);
  ctx.root.querySelector("#save-missed-note")?.addEventListener("click", () => {
    saveMissedNote(courseId, current, ctx.root.querySelector("#missed-note").value);
    ctx.showStatus("Missed-question note saved.");
  });
  ctx.root.querySelector("#study-known")?.addEventListener("click", () => {
    recordQuestionAnswer(courseId, current, current.answer, true, { source: "study" });
    ctx.showStatus("Marked known.");
    ctx.updateChrome();
  });
  ctx.root.querySelector("#study-missed")?.addEventListener("click", () => {
    recordQuestionAnswer(courseId, current, "", false, { source: "study" });
    ctx.showStatus("Marked missed.");
    ctx.updateChrome();
    const missedNotePanel = ctx.root.querySelector("#missed-note-panel");
    if (missedNotePanel) missedNotePanel.hidden = false;
  });

  const keyHandler = (event) => {
    if (!["practice", "study", "review", "bookmarks"].includes(ctx.app.view)) return;
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;

    if (["1", "2", "3", "4"].includes(event.key)) {
      event.preventDefault();
      selectChoice(Number(event.key) - 1);
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const submit = ctx.root.querySelector("#submit-answer");
      if (submit && !submit.disabled) {
        submit.click();
      } else if (ctx.app.view === "study") {
        reveal(false);
      }
    }
    if (event.key.toLowerCase() === "n") {
      event.preventDefault();
      nextQuestion();
    }
    if (event.key.toLowerCase() === "b") {
      event.preventDefault();
      bookmarkButton.click();
    }
  };
  document.addEventListener("keydown", keyHandler);
  ctx.onCleanup(() => document.removeEventListener("keydown", keyHandler));
}
