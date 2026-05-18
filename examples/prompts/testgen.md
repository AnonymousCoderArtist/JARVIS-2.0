---
description: "Generate unit tests for a file or module"
argument-hint: "<file-path>"
---

Write comprehensive unit tests for `$1`.

## Requirements
- Use pytest
- Cover: normal cases, edge cases, error cases
- Mock external dependencies
- Test both success and failure paths
- Include docstrings describing what each test verifies

Place tests in a file mirroring the source structure under `tests/`.
