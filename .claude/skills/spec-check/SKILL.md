---
name: spec-check
description: Audit GWT acceptance specs for implementation language leakage
---

## User Input

```text
$ARGUMENTS
```

## Instructions

Run the spec-guardian agent to audit GWT acceptance specs for implementation leakage.

**If a specific file is provided**: Audit only that file.
**If no file is provided**: Audit all files in `specs/acceptance-specs/*.txt`.

### Steps

1. Check that `specs/acceptance-specs/` directory exists. If not, report: "No acceptance specs directory found. Create specs using the pytest-acceptance-tests skill first."

2. Read the spec file(s) to audit.

3. For each file, parse every GIVEN, WHEN, and THEN statement and check for implementation leakage:

   | Category             | Examples                                                                          |
   | -------------------- | --------------------------------------------------------------------------------- |
   | Code references      | function names, method names, class names, module/package paths, decorators       |
   | Infrastructure       | SQLite, database, table, row, SQL, HTTP, REST, endpoint, JSON, request, response  |
   | Framework language   | use case, port, adapter, repository, handler, dependency injection, fixture       |
   | Technical protocols  | WebSocket, gRPC, TCP, cookie, header, subprocess, stdout/stderr                   |
   | Data structures      | list, dict, tuple, set, dataclass, None, Optional                                 |
   | Internal identifiers | file paths, column names, table names, env variable names, attribute names         |

4. Output a summary table of findings (file, line, statement, category, suggested rewrite).

5. If no violations found, report: "All specs use clean domain language."
