# Generate PBQ Placeholders

Generate performance-based question placeholders when the learner should configure, classify, or assemble a structured response.

Rules:

- Include `scenario` and `task`.
- Use `answer.manualCheck: true` unless the answer can be scored reliably.
- Keep the v0.3 PBQ answer area text-based.
- Include clear reviewer notes in `explanation`.
