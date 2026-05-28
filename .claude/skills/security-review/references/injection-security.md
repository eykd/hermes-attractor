# Injection Security: SQL, Command, Template

## Table of Contents

- [SQL Injection Prevention](#sql-injection-prevention)
- [Command Injection Prevention](#command-injection-prevention)
- [Template Injection & Code Execution](#template-injection--code-execution)

## SQL Injection Prevention

### Parameterized Queries (Required)

Always pass values as query parameters; never build SQL with f-strings, `%`, `.format()`, or `+`.

```python
# ✅ CORRECT - DB-API parameter binding (sqlite3 uses ? placeholders)
user = cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

# ✅ CORRECT - multiple parameters
rows = cursor.execute(
    "SELECT * FROM tasks WHERE user_id = ? AND status = ?",
    (user_id, status),
).fetchall()

# ❌ CRITICAL - f-string interpolation (ruff S608)
cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")

# ❌ CRITICAL - % / .format() / concatenation
cursor.execute("SELECT * FROM users WHERE email = '%s'" % email)
cursor.execute("SELECT * FROM users WHERE email = '{}'".format(email))
```

For SQLAlchemy, use bound parameters or the ORM, never `text()` with interpolation:

```python
from sqlalchemy import text

# ✅ bound parameters
conn.execute(text("SELECT * FROM users WHERE id = :id"), {"id": user_id})

# ❌ interpolated text() (ruff S608)
conn.execute(text(f"SELECT * FROM users WHERE id = {user_id}"))
```

### Dynamic Query Building

Build the *structure* statically with placeholders, and pass only values as parameters:

```python
def build_query(filters: TaskFilters) -> tuple[str, list[object]]:
    conditions = ["user_id = ?"]
    params: list[object] = [filters.user_id]

    if filters.status is not None:
        conditions.append("status = ?")
        params.append(filters.status)
    if filters.created_after is not None:
        conditions.append("created_at > ?")
        params.append(filters.created_after.isoformat())

    sql = f"SELECT * FROM tasks WHERE {' AND '.join(conditions)} LIMIT ?"  # placeholders only, no values
    params.append(filters.limit or 50)
    return sql, params
```

### Safe Dynamic Identifiers (table/column names)

Identifiers can't be parameterized, so validate against an allowlist before interpolating:

```python
_ALLOWED_COLUMNS = frozenset({"created_at", "updated_at", "title", "status"})
_ALLOWED_DIRECTIONS = frozenset({"ASC", "DESC"})


def order_clause(column: str, direction: str) -> str:
    if column not in _ALLOWED_COLUMNS:
        msg = f"Invalid column: {column}"
        raise ValueError(msg)
    direction = direction.upper()
    if direction not in _ALLOWED_DIRECTIONS:
        msg = f"Invalid direction: {direction}"
        raise ValueError(msg)
    return f"ORDER BY {column} {direction}"  # safe: both halves are from allowlists
```

### Flag These as Critical

- Any f-string, `%`, `.format()`, or `+` building a SQL string with user input
- `text()` (SQLAlchemy) with interpolated values
- Dynamic table/column names without an allowlist
- Raw `execute` of a fully-formatted string

## Command Injection Prevention

### Never use shell=True with untrusted input

Pass an argv **list** so the OS does not invoke a shell that interprets metacharacters.

```python
import subprocess

# ✅ CORRECT - argv list, no shell
subprocess.run(["convert", filename, "out.png"], check=True)

# ✅ CORRECT - capture output safely
result = subprocess.run(["git", "rev-parse", rev], capture_output=True, text=True, check=True)

# ❌ CRITICAL - shell=True with interpolation (ruff S602)
subprocess.run(f"convert {filename} out.png", shell=True)

# ❌ CRITICAL - os.system always uses a shell (ruff S605)
os.system(f"rm {path}")
```

If you truly need shell features, never feed user input into the command string; if unavoidable, escape with `shlex.quote` — but prefer an argv list.

```python
import shlex

cmd = f"grep {shlex.quote(pattern)} file.txt"  # last resort only
```

### Use full executable paths or a known PATH

`subprocess` with a partial executable name (`"git"`) trusts `PATH`; ruff `S607` flags this. In security-sensitive contexts, pass an absolute path or control the environment.

### Flag These as High/Critical

- `shell=True` anywhere user input reaches the command (ruff `S602`, `S604`) — Critical if interpolated
- `os.system`, `os.popen` with dynamic input (ruff `S605`)
- Partial executable paths in privileged contexts (ruff `S607`)

## Template Injection & Code Execution

### Jinja2: keep autoescaping on

```python
from jinja2 import Environment, select_autoescape

# ✅ autoescape enabled for HTML/XML
env = Environment(autoescape=select_autoescape(["html", "xml"]))

# ❌ autoescape off → XSS when rendering user data into HTML
env = Environment(autoescape=False)
```

Never build a template from user input (`Template(user_input)`) — that is server-side template injection (SSTI), equivalent to code execution.

### Never eval/exec untrusted input

```python
# ❌ CRITICAL (ruff S307 for eval)
eval(user_input)
exec(user_input)

# ✅ For parsing structured data, use a safe parser:
import ast
value = ast.literal_eval(user_input)  # only literals, no code execution
```

### Flag These as Critical

- `eval` / `exec` with any external input (ruff `S307`)
- `jinja2.Template(user_input)` or `Environment(autoescape=False)` rendering user data
- `__import__` / `getattr(obj, user_controlled_name)` reaching attacker input
- Format-string attacks: `user_format.format(obj)` where `user_format` is attacker-controlled (can read attributes)
