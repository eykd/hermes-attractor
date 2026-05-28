# Deserialization & Untrusted Data

## Table of Contents

- [Insecure Deserialization](#insecure-deserialization)
- [Path Traversal](#path-traversal)
- [XML / XXE](#xml--xxe)
- [SSRF and Unsafe Fetches](#ssrf-and-unsafe-fetches)
- [TLS Verification](#tls-verification)

## Insecure Deserialization

### pickle / marshal / shelve

`pickle.loads` can execute arbitrary code during deserialization. Never unpickle data from an untrusted source.

```python
import pickle

# ❌ CRITICAL - remote code execution if bytes are attacker-controlled (ruff S301)
obj = pickle.loads(untrusted_bytes)

# ✅ Use a data-only format for untrusted input
import json
obj = json.loads(untrusted_text)
```

The same applies to `marshal.loads` and `shelve` (which uses pickle under the hood).

### YAML

`yaml.load` without a safe loader can construct arbitrary Python objects.

```python
import yaml

# ❌ CRITICAL - arbitrary object construction (ruff S506)
data = yaml.load(untrusted_text)
data = yaml.load(untrusted_text, Loader=yaml.Loader)

# ✅ CORRECT - safe loader only handles standard scalars/collections
data = yaml.safe_load(untrusted_text)
```

### Flag These as Critical

- `pickle.loads` / `pickle.load` / `cPickle` on data crossing a trust boundary (ruff `S301`)
- `marshal.loads`, `shelve` with untrusted files
- `yaml.load` without `SafeLoader` (ruff `S506`)
- `jsonpickle.decode` on untrusted input

## Path Traversal

Joining user-supplied names into a filesystem path lets `../` escape the intended directory.

```python
from pathlib import Path

BASE = Path("/srv/uploads").resolve()


def safe_open(user_filename: str) -> Path:
    target = (BASE / user_filename).resolve()
    # ✅ Reject anything that resolves outside BASE (handles ../, symlinks, abs paths)
    if not target.is_relative_to(BASE):
        msg = "Invalid path"
        raise ValueError(msg)
    return target
```

```python
# ❌ HIGH - user input controls the path with no containment check
open(os.path.join(base_dir, user_filename))
Path(base_dir, request.params["file"]).read_text()
```

Also reject `..`, leading `/`, and backslashes in uploaded file *names* before using them.

### Flag These as High

- Opening/reading/writing a path built from user input without a containment check
- `os.path.join` / `Path(...)` with request data and no `is_relative_to(base)` guard
- Extracting archives (`zipfile`, `tarfile`) without validating member paths (zip-slip) — use `extractall(filter="data")` on 3.12+ or validate each member

## XML / XXE

The stdlib `xml.etree`, `xml.dom`, and `xml.sax` are vulnerable to entity-expansion and external-entity attacks on untrusted input (ruff `S313`–`S320`).

```python
# ❌ HIGH - XXE / billion-laughs on untrusted XML
import xml.etree.ElementTree as ET
tree = ET.fromstring(untrusted_xml)

# ✅ Use defusedxml for untrusted input
from defusedxml.ElementTree import fromstring
tree = fromstring(untrusted_xml)
```

### Flag These as High

- Parsing untrusted XML with stdlib `xml.*` instead of `defusedxml`

## SSRF and Unsafe Fetches

Fetching a user-supplied URL lets an attacker reach internal services (cloud metadata, localhost, internal APIs).

```python
# ❌ HIGH - server-side request forgery
import httpx
httpx.get(request.params["url"])

# ✅ Validate scheme + host against an allowlist before fetching
from urllib.parse import urlparse

ALLOWED_HOSTS = frozenset({"api.partner.example.com"})


def safe_fetch(url: str) -> httpx.Response:
    parsed = urlparse(url)
    if parsed.scheme not in {"https"} or parsed.hostname not in ALLOWED_HOSTS:
        msg = "URL not allowed"
        raise ValueError(msg)
    return httpx.get(url, timeout=5.0)
```

### Flag These as High

- `httpx`/`requests`/`urllib.request.urlopen` on a URL derived from user input without host allowlisting (ruff `S310` for `urlopen`)
- Following redirects to internal hosts

## TLS Verification

```python
# ❌ HIGH - disables certificate verification (ruff S501)
httpx.get(url, verify=False)
requests.get(url, verify=False)
ssl._create_unverified_context()

# ✅ Verification on by default — just don't turn it off
httpx.get(url)  # verify=True is the default
```

### Flag These as High

- `verify=False` on any HTTP client (ruff `S501`)
- `ssl.CERT_NONE` / `_create_unverified_context` (ruff `S323`)
