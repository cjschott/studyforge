import { getCourseState, recordFlashcard } from "./storage.js";

function unique(values) {
  return Array.from(new Set(values.filter(Boolean))).sort();
}

export function renderFlashcards(ctx) {
  const courseId = ctx.bundle.meta.id;
  const courseState = getCourseState(courseId);
  const topics = unique(ctx.bundle.flashcards.map((card) => card.topic));
  const topic = ctx.params.topic || "";
  const pool = topic ? ctx.bundle.flashcards.filter((card) => card.topic === topic) : ctx.bundle.flashcards;
  const requested = pool.findIndex((card) => card.id === ctx.params.cardId);
  const index = requested >= 0 ? requested : Math.min(Number(ctx.params.index || 0), Math.max(pool.length - 1, 0));
  const card = pool[index];
  const flipped = Boolean(ctx.params.flipped);

  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Flashcards</h2>
        <p class="muted">Space flips, right arrow advances, 1 marks known, 2 marks missed.</p>
      </div>
      <span class="tag blue">${pool.length} cards</span>
    </div>

    <section class="card">
      <form id="flashcard-filter" class="filter-grid">
        <div class="field">
          <label for="flashcard-topic">Topic</label>
          <select id="flashcard-topic" class="course-select" name="topic">
            <option value="">All topics</option>
            ${topics.map((item) => `<option value="${item}" ${item === topic ? "selected" : ""}>${item}</option>`).join("")}
          </select>
        </div>
        <button class="button button-primary" type="submit">Apply</button>
      </form>
    </section>

    ${card ? `
      <section class="card" style="margin-top: 1rem;">
        <div class="button-row" style="justify-content: space-between;">
          <div class="button-row">
            <span class="tag blue">${card.topic}</span>
            <span class="tag">${index + 1} / ${pool.length}</span>
          </div>
          <span class="muted">Known ${courseState.flashcards?.[card.id]?.known || 0} · Missed ${courseState.flashcards?.[card.id]?.missed || 0}</span>
        </div>
        <button id="flashcard-card" class="flashcard" type="button" aria-label="Flip flashcard">
          <p>${flipped ? card.back : card.front}</p>
        </button>
        ${flipped && card.memory ? `<p class="muted"><strong>Memory:</strong> ${card.memory}</p>` : ""}
        <div class="button-row" style="margin-top: 1rem;">
          <button id="card-known" class="button button-success" type="button">Known</button>
          <button id="card-missed" class="button button-danger" type="button">Missed</button>
          <button id="card-next" class="button" type="button">Next</button>
        </div>
      </section>
    ` : `
      <section class="empty-state">
        <h2>No flashcards match this topic.</h2>
        <p>Choose another topic or add cards to this course pack.</p>
      </section>
    `}
  `;

  ctx.root.querySelector("#flashcard-filter").addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    ctx.navigate("flashcards", { topic: data.get("topic"), index: 0 });
  });

  if (!card) return;

  const next = () => {
    ctx.navigate("flashcards", { topic, index: (index + 1) % pool.length, flipped: false });
  };
  const mark = (result) => {
    recordFlashcard(courseId, card, result);
    ctx.showStatus(result === "known" ? "Marked known." : "Marked missed.");
    next();
  };

  ctx.root.querySelector("#flashcard-card").addEventListener("click", () => {
    ctx.navigate("flashcards", { topic, index, flipped: !flipped });
  });
  ctx.root.querySelector("#card-known").addEventListener("click", () => mark("known"));
  ctx.root.querySelector("#card-missed").addEventListener("click", () => mark("missed"));
  ctx.root.querySelector("#card-next").addEventListener("click", next);

  const keyHandler = (event) => {
    if (ctx.app.view !== "flashcards") return;
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;
    if (event.code === "Space") {
      event.preventDefault();
      ctx.navigate("flashcards", { topic, index, flipped: !flipped });
    }
    if (event.code === "ArrowRight") next();
    if (event.key === "1") mark("known");
    if (event.key === "2") mark("missed");
  };
  document.addEventListener("keydown", keyHandler);
  ctx.onCleanup(() => document.removeEventListener("keydown", keyHandler));
}
