function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function valuesEqual(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function normalize(value) {
  if (Array.isArray(value)) return value.map(normalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, normalize(value[key])]));
  }
  return value;
}

export function questionType(question) {
  return question.type || question.questionType || question.question_type || "single_choice";
}

export function formatAnswer(answer) {
  if (Array.isArray(answer)) return answer.join(", ");
  if (answer && typeof answer === "object") {
    if (answer.manualCheck) return "Manual review";
    return Object.entries(answer).map(([key, value]) => `${key}: ${value}`).join("; ");
  }
  return String(answer ?? "");
}

export function renderQuestionMedia(question) {
  const image = question.image || question.imagePath;
  if (!image) return "";
  return `<img class="question-image" src="${escapeHtml(image)}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('p'),{className:'helper-text',textContent:'Diagram image unavailable.'}))">`;
}

function renderChoiceQuestion(question, name, selected, multiple = false) {
  const selectedSet = new Set(Array.isArray(selected) ? selected : [selected]);
  const inputType = multiple ? "checkbox" : "radio";
  return `
    <div class="choice-list" data-question-control="${multiple ? "multi_select" : "single_choice"}">
      ${(question.choices || []).map((choice, index) => `
        <label class="choice ${selectedSet.has(choice) ? "selected" : ""}" data-choice-index="${index}">
          <input data-question-input type="${inputType}" name="${name}" value="${index}" ${selectedSet.has(choice) ? "checked" : ""}>
          <span>${escapeHtml(choice)}</span>
        </label>
      `).join("")}
    </div>
  `;
}

function renderMatchingQuestion(question, selected = {}) {
  const choices = question.choices || {};
  const left = choices.left || [];
  const right = choices.right || [];
  return `
    <div class="matching-list" data-question-control="matching">
      ${left.map((item, index) => `
        <label class="match-row">
          <span>${escapeHtml(item)}</span>
          <select data-question-input data-match-left="${index}" class="course-select">
            <option value="">Select match</option>
            ${right.map((choice) => `<option value="${escapeHtml(choice)}" ${selected[item] === choice ? "selected" : ""}>${escapeHtml(choice)}</option>`).join("")}
          </select>
        </label>
      `).join("")}
    </div>
  `;
}

function renderOrderingQuestion(question, selected = []) {
  const choices = question.choices || [];
  return `
    <div class="ordering-list" data-question-control="ordering">
      ${choices.map((item, index) => `
        <label class="order-row">
          <select data-question-input data-order-index="${index}" class="course-select">
            <option value="">Order</option>
            ${choices.map((_, orderIndex) => `<option value="${orderIndex}" ${selected[orderIndex] === item ? "selected" : ""}>${orderIndex + 1}</option>`).join("")}
          </select>
          <span>${escapeHtml(item)}</span>
        </label>
      `).join("")}
    </div>
  `;
}

function renderPbqQuestion(question, selected = "") {
  return `
    <div class="pbq-box" data-question-control="pbq">
      ${question.scenario ? `<p class="muted">${escapeHtml(question.scenario)}</p>` : ""}
      ${question.task ? `<p>${escapeHtml(question.task)}</p>` : ""}
      <textarea data-question-input class="textarea" placeholder="Enter your structured response">${escapeHtml(selected)}</textarea>
    </div>
  `;
}

export function renderQuestionControl(question, name = "answer-choice", selected = null) {
  const type = questionType(question);
  if (type === "multi_select") return renderChoiceQuestion(question, name, selected || [], true);
  if (type === "matching") return renderMatchingQuestion(question, selected || {});
  if (type === "ordering") return renderOrderingQuestion(question, selected || []);
  if (type === "pbq") return renderPbqQuestion(question, selected || "");
  return renderChoiceQuestion(question, name, selected, false);
}

export function collectAnswer(root, question, name = "answer-choice") {
  const type = questionType(question);
  if (type === "multi_select") {
    return Array.from(root.querySelectorAll(`input[name='${name}']:checked`)).map((input) => question.choices[Number(input.value)]);
  }
  if (type === "matching") {
    const choices = question.choices || {};
    const left = choices.left || [];
    const result = {};
    root.querySelectorAll("[data-match-left]").forEach((select) => {
      const item = left[Number(select.dataset.matchLeft)];
      if (item && select.value) result[item] = select.value;
    });
    return result;
  }
  if (type === "ordering") {
    const ordered = [];
    root.querySelectorAll("[data-order-index]").forEach((select) => {
      if (select.value !== "") {
        ordered[Number(select.value)] = question.choices[Number(select.dataset.orderIndex)];
      }
    });
    return ordered.filter(Boolean);
  }
  if (type === "pbq") {
    return root.querySelector("[data-question-control='pbq'] textarea")?.value.trim() || "";
  }
  const input = root.querySelector(`input[name='${name}']:checked`);
  return input ? question.choices[Number(input.value)] : "";
}

export function hasAnswer(question, selected) {
  const type = questionType(question);
  if (type === "multi_select" || type === "ordering") return Array.isArray(selected) && selected.length > 0;
  if (type === "matching") return selected && Object.keys(selected).length > 0;
  return selected !== "";
}

export function scoreQuestion(question, selected) {
  const type = questionType(question);
  const expected = question.answer;
  if (type === "multi_select" && Array.isArray(expected) && Array.isArray(selected)) {
    return expected.map(String).sort().join("|") === selected.map(String).sort().join("|");
  }
  if (type === "pbq" && expected && typeof expected === "object" && expected.manualCheck) {
    return false;
  }
  if (type === "pbq") {
    return String(selected || "").trim().toLowerCase() === String(expected || "").trim().toLowerCase();
  }
  return valuesEqual(normalize(selected), normalize(expected));
}

export function markQuestionResult(root, question, selected, name = "answer-choice") {
  const type = questionType(question);
  if (type === "single_choice" || type === "diagram") {
    const correctIndex = (question.choices || []).findIndex((choice) => choice === question.answer);
    const selectedIndex = (question.choices || []).findIndex((choice) => choice === selected);
    root.querySelectorAll(".choice").forEach((choiceEl) => {
      const index = Number(choiceEl.dataset.choiceIndex);
      choiceEl.classList.toggle("selected", index === selectedIndex);
      choiceEl.classList.toggle("correct", index === correctIndex);
      choiceEl.classList.toggle("wrong", selectedIndex >= 0 && index === selectedIndex && index !== correctIndex);
      choiceEl.querySelector("input").disabled = true;
    });
    return;
  }
  if (type === "multi_select") {
    const correct = new Set(question.answer || []);
    const selectedSet = new Set(selected || []);
    root.querySelectorAll(".choice").forEach((choiceEl) => {
      const value = question.choices[Number(choiceEl.dataset.choiceIndex)];
      choiceEl.classList.toggle("selected", selectedSet.has(value));
      choiceEl.classList.toggle("correct", correct.has(value));
      choiceEl.classList.toggle("wrong", selectedSet.has(value) && !correct.has(value));
      choiceEl.querySelector("input").disabled = true;
    });
    return;
  }
  root.querySelectorAll("[data-question-input]").forEach((input) => {
    input.disabled = true;
  });
  root.querySelector("[data-question-control]")?.classList.add(scoreQuestion(question, selected) ? "correct-complex" : "wrong-complex");
}
