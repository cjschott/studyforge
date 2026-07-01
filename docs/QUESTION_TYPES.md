# Question Types

StudyForge v0.3 supports a foundation for these types.

## single_choice

Uses radio buttons. `answer` is one choice string.

## multi_select

Uses checkboxes. `answer` is an array of correct choice strings.

## matching

Uses dropdowns.

```json
{
  "choices": {
    "left": ["Authentication"],
    "right": ["Proves identity"]
  },
  "answer": {
    "Authentication": "Proves identity"
  }
}
```

## ordering

Uses order selectors. `answer` is the correct ordered array.

## diagram

Uses an optional `image` path plus normal choices. Clickable regions are future work.

## pbq

Uses scenario/task text and a structured text response. v0.3 supports manual-check placeholders with:

```json
{
  "answer": {
    "manualCheck": true,
    "expected": ["Expected action"]
  }
}
```
