"""Guard mini-language evaluator for Attractor pipeline edge conditions.

The guard language is a restricted, total, purely-domain expression language.
It MUST NOT use eval/exec/compile — it is a custom recursive-descent parser.

Grammar (EBNF):
  expr       ::= or_expr
  or_expr    ::= and_expr ( "or" and_expr )*
  and_expr   ::= not_expr ( "and" not_expr )*
  not_expr   ::= "not" not_expr | atom
  atom       ::= "(" expr ")" | comparison
  comparison ::= operand ( cmp_op operand )?
  operand    ::= KEY | STRING | NUMBER | BOOL | NULL
  cmp_op     ::= "==" | "!=" | "<" | "<=" | ">" | ">="
  KEY        ::= [A-Za-z_][A-Za-z0-9_.]* (max 64 chars, max 4 dot-segments)
  STRING     ::= quoted string literal (single or double quotes, no embedded newlines)
  NUMBER     ::= integer or decimal literal
  BOOL       ::= "true" | "false"
  NULL       ::= "null"

Safety constraints (FR-011 / plan.md §Security):
  - Guard strings > 512 chars raise PipelineValidationError at call time.
  - Parse-tree nesting depth > 32 raises PipelineValidationError (not RecursionError).
  - Malformed guards raise PipelineValidationError (not SyntaxError).
  - Missing context keys, non-mapping intermediates, and type mismatches are all
    handled as falsy — never exceptions.

See: specs/001-attractor-kanban/plan.md §Security §Guard/condition evaluation
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hermes_attractor.domain.constants import MAX_GUARD_DEPTH, MAX_GUARD_LENGTH
from hermes_attractor.domain.exceptions import PipelineValidationError, ValidationIssue

if TYPE_CHECKING:
    from collections.abc import Mapping

#: Maximum number of dot-path segments for a KEY operand.
_MAX_KEY_SEGMENTS: int = 4


# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_TOKEN_SPEC = [
    ("OP2", r"==|!=|<=|>="),
    ("OP1", r"[<>()]"),
    ("NUMBER", r"-?\d+(?:\.\d+)?"),
    ("STRING", r'"[^"\n]*"|\'[^\'\n]*\''),
    ("BOOL", r"\b(?:true|false)\b"),
    ("NULL", r"\bnull\b"),
    ("AND", r"\band\b"),
    ("OR", r"\bor\b"),
    ("NOT", r"\bnot\b"),
    ("KEY", r"[A-Za-z_][A-Za-z0-9_.]*"),
    ("WS", r"\s+"),
]

_TOKEN_RE = re.compile("|".join(f"(?P<{name}>{pat})" for name, pat in _TOKEN_SPEC))


@dataclass
class _Token:
    """A single lexed token.

    Attributes:
        kind: Token type name (e.g. ``KEY``, ``STRING``, ``OP2``).
        value: Raw matched string.
    """

    kind: str
    value: str


def _tokenise(guard: str) -> list[_Token]:
    """Tokenise a guard expression string.

    Args:
        guard: The raw guard expression string.

    Returns:
        A list of Token objects (whitespace excluded).

    Raises:
        PipelineValidationError: If an unrecognised character sequence is encountered.
    """
    tokens: list[_Token] = []
    pos = 0
    while pos < len(guard):
        m = _TOKEN_RE.match(guard, pos)
        if m is None:
            msg = f"Unrecognised character at position {pos}: {guard[pos]!r}"
            raise PipelineValidationError(
                issues=[ValidationIssue(element_id="guard", reason=msg)],
                message="Guard parse error",
            )
        kind = m.lastgroup
        if kind is None:  # pragma: no cover  # regex always sets lastgroup on a match
            break
        if kind != "WS":
            tokens.append(_Token(kind=kind, value=m.group()))
        pos = m.end()
    return tokens


# ---------------------------------------------------------------------------
# Parser state
# ---------------------------------------------------------------------------


@dataclass
class _Parser:
    """Recursive-descent parser state for the guard mini-language.

    Attributes:
        tokens: The token stream.
        pos: Current position in the token stream.
        depth: Current recursion depth (incremented per nested call).
    """

    tokens: list[_Token]
    pos: int = field(default=0)
    depth: int = field(default=0)

    def peek(self) -> _Token | None:
        """Return the next token without consuming it."""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, *kinds: str) -> _Token:
        """Consume and return the next token, asserting it is one of the given kinds.

        Args:
            kinds: Acceptable token kinds.

        Returns:
            The consumed token.

        Raises:
            PipelineValidationError: If the next token is not one of the expected kinds.
        """
        tok = self.peek()
        if tok is None or tok.kind not in kinds:
            msg = f"Expected {kinds!r} but got {tok!r} at position {self.pos}"
            raise PipelineValidationError(
                issues=[ValidationIssue(element_id="guard", reason=msg)],
                message="Guard parse error",
            )
        self.pos += 1
        return tok


# ---------------------------------------------------------------------------
# Recursive descent parse + eval
# ---------------------------------------------------------------------------


def _check_parser_depth(parser: _Parser) -> None:
    """Raise PipelineValidationError if the parser nesting depth exceeds MAX_GUARD_DEPTH.

    Args:
        parser: The parser whose depth to check.

    Raises:
        PipelineValidationError: If depth > MAX_GUARD_DEPTH.
    """
    if parser.depth > MAX_GUARD_DEPTH:
        msg = f"Guard nesting depth exceeds maximum of {MAX_GUARD_DEPTH}"
        raise PipelineValidationError(
            issues=[ValidationIssue(element_id="guard", reason=msg)],
            message="Guard nesting too deep",
        )


def _resolve_key(key: str, ctx: Mapping[str, object]) -> object:
    """Resolve a dot-path key against a context mapping.

    Dot-path traversal is total: missing keys, non-mapping intermediates, and
    more than 4 segments all yield ``None`` (falsy) rather than raising.

    Args:
        key: The dot-path key string (e.g. ``"status"`` or ``"a.b.c"``).
        ctx: The context mapping.

    Returns:
        The resolved value, or ``None`` for any missing/invalid path.
    """
    segments = key.split(".")
    if len(segments) > _MAX_KEY_SEGMENTS:
        return None
    if not isinstance(ctx, dict):  # pragma: no cover  # defensive; callers always pass dicts
        return None
    current: dict[str, object] = ctx
    for i, segment in enumerate(segments):
        value: object = current.get(segment)
        if value is None:
            return None
        if i < len(segments) - 1:
            if not isinstance(value, dict):
                return None
            current = value  # pyright: ignore[reportUnknownVariableType]
        else:
            return value
    return None  # pragma: no cover  # loop always returns via the else branch


def _parse_operand(parser: _Parser, ctx: Mapping[str, object]) -> object:
    """Parse and evaluate a single operand.

    Args:
        parser: The parser state.
        ctx: The evaluation context.

    Returns:
        The evaluated operand value.

    Raises:
        PipelineValidationError: On unexpected token.
    """
    tok = parser.peek()
    if tok is None:
        msg = "Expected operand but got end of input"
        raise PipelineValidationError(
            issues=[ValidationIssue(element_id="guard", reason=msg)],
            message="Guard parse error",
        )
    if tok.kind == "STRING":
        parser.pos += 1
        return tok.value[1:-1]  # strip quotes
    if tok.kind == "NUMBER":
        parser.pos += 1
        return float(tok.value) if "." in tok.value else int(tok.value)
    if tok.kind == "BOOL":
        parser.pos += 1
        return tok.value == "true"
    if tok.kind == "NULL":
        parser.pos += 1
        return None
    if tok.kind == "KEY":
        parser.pos += 1
        return _resolve_key(tok.value, ctx)
    msg = f"Unexpected token {tok!r} where operand expected"
    raise PipelineValidationError(
        issues=[ValidationIssue(element_id="guard", reason=msg)],
        message="Guard parse error",
    )


def _compare(op: str, left: object, right: object) -> bool:
    """Apply a binary comparison operator to two values.

    Returns False on any type mismatch or ordering error (total).

    Args:
        op: One of ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``.
        left: The left operand.
        right: The right operand.

    Returns:
        Boolean result; False on type errors.
    """
    try:
        result = (
            (left == right)
            if op == "=="
            else (left != right)
            if op == "!="
            else bool(left < right)  # type: ignore[operator]
            if op == "<"
            else bool(left <= right)  # type: ignore[operator]
            if op == "<="
            else bool(left > right)  # type: ignore[operator]
            if op == ">"
            else bool(left >= right)  # type: ignore[operator]
        )
        return bool(result)
    except (TypeError, ValueError):
        return False


def _parse_comparison(parser: _Parser, ctx: Mapping[str, object]) -> bool:
    """Parse and evaluate a comparison expression.

    Args:
        parser: The parser state.
        ctx: The evaluation context.

    Returns:
        Boolean result of the comparison.
    """
    left = _parse_operand(parser, ctx)
    tok = parser.peek()
    if tok is None or tok.kind not in ("OP2", "OP1"):
        return bool(left)
    op = tok.value
    if op not in ("==", "!=", "<", "<=", ">", ">="):
        return bool(left)
    parser.pos += 1
    right = _parse_operand(parser, ctx)
    return _compare(op, left, right)


def _parse_atom(parser: _Parser, ctx: Mapping[str, object]) -> bool:
    """Parse and evaluate an atom (parenthesised expr or comparison).

    Args:
        parser: The parser state.
        ctx: The evaluation context.

    Returns:
        Boolean result.
    """
    parser.depth += 1
    _check_parser_depth(parser)
    tok = parser.peek()
    if tok is not None and tok.kind == "OP1" and tok.value == "(":
        parser.pos += 1
        result = _parse_expr(parser, ctx)
        _ = parser.consume("OP1")  # closing )
        parser.depth -= 1
        return result
    result = _parse_comparison(parser, ctx)
    parser.depth -= 1
    return result


def _parse_not(parser: _Parser, ctx: Mapping[str, object]) -> bool:
    """Parse and evaluate a not_expr.

    Args:
        parser: The parser state.
        ctx: The evaluation context.

    Returns:
        Boolean result.
    """
    tok = parser.peek()
    if tok is not None and tok.kind == "NOT":
        parser.depth += 1
        _check_parser_depth(parser)
        parser.pos += 1
        result = not _parse_not(parser, ctx)
        parser.depth -= 1
        return result
    return _parse_atom(parser, ctx)


def _parse_and(parser: _Parser, ctx: Mapping[str, object]) -> bool:
    """Parse and evaluate an and_expr.

    Args:
        parser: The parser state.
        ctx: The evaluation context.

    Returns:
        Boolean result.
    """
    result = _parse_not(parser, ctx)
    while True:
        tok = parser.peek()
        if tok is None or tok.kind != "AND":
            break
        parser.pos += 1
        right = _parse_not(parser, ctx)  # always parse to advance position
        result = result and right
    return result


def _parse_or(parser: _Parser, ctx: Mapping[str, object]) -> bool:
    """Parse and evaluate an or_expr.

    Args:
        parser: The parser state.
        ctx: The evaluation context.

    Returns:
        Boolean result.
    """
    result = _parse_and(parser, ctx)
    while True:
        tok = parser.peek()
        if tok is None or tok.kind != "OR":
            break
        parser.pos += 1
        right = _parse_and(parser, ctx)  # always parse to advance position
        result = result or right
    return result


def _parse_expr(parser: _Parser, ctx: Mapping[str, object]) -> bool:
    """Parse and evaluate a top-level expression.

    Args:
        parser: The parser state.
        ctx: The evaluation context.

    Returns:
        Boolean result.
    """
    return _parse_or(parser, ctx)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate(guard: str, context: Mapping[str, object]) -> bool:
    """Evaluate a guard expression against a context mapping.

    This is a pure, total function — it never raises for missing keys or type
    mismatches; those are silently falsy. It raises PipelineValidationError for
    structurally invalid guards (too long, too deep, or unparseable).

    Args:
        guard: The guard expression string.
        context: The pipeline run context to evaluate against.

    Returns:
        True if the guard condition is satisfied, False otherwise.

    Raises:
        PipelineValidationError: If the guard is too long, too deeply nested,
            or cannot be parsed.
    """
    if len(guard) > MAX_GUARD_LENGTH:
        msg = f"Guard expression exceeds maximum length of {MAX_GUARD_LENGTH} characters"
        raise PipelineValidationError(
            issues=[ValidationIssue(element_id="guard", reason=msg)],
            message="Guard too long",
        )
    tokens = _tokenise(guard)
    parser = _Parser(tokens=tokens)
    result = _parse_expr(parser, context)
    if parser.pos < len(parser.tokens):
        msg = f"Unexpected token at position {parser.pos}: {parser.tokens[parser.pos]!r}"
        raise PipelineValidationError(
            issues=[ValidationIssue(element_id="guard", reason=msg)],
            message="Guard parse error",
        )
    return result
