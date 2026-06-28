function searchableText(parts) {
  return parts.flat().filter(Boolean).join(" ").toLowerCase();
}

function snippet(text, query) {
  const source = String(text || "");
  const lower = source.toLowerCase();
  const index = lower.indexOf(query.toLowerCase());
  if (index < 0) return source.slice(0, 180);
  const start = Math.max(0, index - 60);
  return `${start > 0 ? "..." : ""}${source.slice(start, start + 180)}${start + 180 < source.length ? "..." : ""}`;
}

function buildResults(bundle, query) {
  if (!query) return [];
  const results = [];

  bundle.questions.forEach((question) => {
    const text = searchableText([question.question, question.choices, question.explanation, question.memory, question.examTip, question.topic, question.subtopic]);
    if (text.includes(query)) {
      results.push({
        type: "Question",
        topic: question.topic,
        title: question.question,
        snippet: snippet(`${question.question} ${question.explanation}`, query),
        targetView: "practice",
        targetParams: { questionId: question.id }
      });
    }
  });

  bundle.flashcards.forEach((card) => {
    const text = searchableText([card.front, card.back, card.memory, card.topic]);
    if (text.includes(query)) {
      results.push({
        type: "Flashcard",
        topic: card.topic,
        title: card.front,
        snippet: snippet(`${card.front} ${card.back}`, query),
        targetView: "flashcards",
        targetParams: { cardId: card.id, flipped: false }
      });
    }
  });

  bundle.glossary.forEach((term) => {
    const text = searchableText([term.term, term.definition, term.examTip, term.relatedTerms, term.topic]);
    if (text.includes(query)) {
      results.push({
        type: "Glossary",
        topic: term.topic || "Glossary",
        title: term.term,
        snippet: snippet(term.definition, query),
        targetView: "studyGuide",
        targetParams: { query: term.term }
      });
    }
  });

  bundle.cheatsheets.forEach((sheet) => {
    const text = searchableText([sheet.title, sheet.topic, JSON.stringify(sheet.content)]);
    if (text.includes(query)) {
      results.push({
        type: "Cheat Sheet",
        topic: sheet.topic,
        title: sheet.title,
        snippet: snippet(JSON.stringify(sheet.content), query),
        targetView: "studyGuide",
        targetParams: { query: sheet.title }
      });
    }
  });

  return results.slice(0, 80);
}

export function renderSearch(ctx) {
  const query = String(ctx.params.query || "").trim().toLowerCase();
  const results = buildResults(ctx.bundle, query);

  ctx.root.innerHTML = `
    <div class="view-header">
      <div>
        <h2>Search</h2>
        <p class="muted">Search questions, answers, explanations, flashcards, glossary terms, and cheat sheets.</p>
      </div>
    </div>

    <section class="card">
      <form id="global-search-form" class="filter-grid">
        <div class="field">
          <label for="global-search">Search StudyForge</label>
          <input id="global-search" class="input" name="query" type="search" value="${ctx.params.query || ""}" placeholder="Try CDMA, WDM, CRC, APIPA, 802.11ax">
        </div>
        <button class="button button-primary" type="submit">Search</button>
      </form>
    </section>

    <div class="section-title">
      <h3>Results</h3>
      <span class="muted">${query ? `${results.length} matches` : "Enter a search term"}</span>
    </div>
    <section class="grid">
      ${query ? results.map((result, index) => `
        <button class="search-result" type="button" data-index="${index}">
          <div class="button-row">
            <span class="tag blue">${result.type}</span>
            <span class="tag">${result.topic}</span>
          </div>
          <h3>${result.title}</h3>
          <p class="muted">${result.snippet}</p>
        </button>
      `).join("") || `
        <article class="empty-state">
          <h2>No matches found.</h2>
          <p>Try a shorter term or acronym.</p>
        </article>
      ` : `
        <article class="empty-state">
          <h2>Search your course pack.</h2>
          <p>Results open the relevant question, flashcard, glossary term, or cheat sheet.</p>
        </article>
      `}
    </section>
  `;

  ctx.root.querySelector("#global-search-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    ctx.navigate("search", { query: String(data.get("query") || "").trim() });
  });

  ctx.root.querySelectorAll(".search-result").forEach((button) => {
    button.addEventListener("click", () => {
      const result = results[Number(button.dataset.index)];
      ctx.navigate(result.targetView, result.targetParams);
    });
  });
}
