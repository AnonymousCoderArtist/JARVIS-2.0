---
description: "Perform a thorough code review of the current changes"
argument-hint: "<branch>"
---

Perform a detailed code review of the changes in branch `$1`.

## Checklist
1. Are there logic errors or bugs?
2. Is there adequate test coverage?
3. Are there performance or security concerns?
4. Does the code follow project conventions?
5. Are there any edge cases not handled?

Format findings as:
- **Severity**: Bug/Risk/Concern/Suggestion
- **Location**: file:line
- **Description**: What's wrong
- **Fix**: How to fix it
