# Generate Matching Questions

Generate matching questions for definitions, ports, phases, tools, or protocol mappings.

Use this shape:

```json
{
  "choices": {
    "left": ["Term A", "Term B"],
    "right": ["Definition A", "Definition B"]
  },
  "answer": {
    "Term A": "Definition A",
    "Term B": "Definition B"
  }
}
```

Keep left and right lists concise enough for mobile rendering.
