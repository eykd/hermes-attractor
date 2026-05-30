"""Unit tests for the guard mini-language evaluator (RED phase for M1).

Tests fail until src/hermes_attractor/domain/guard.py is implemented.
"""

from __future__ import annotations

import pytest

from hermes_attractor.domain.exceptions import PipelineValidationError
from hermes_attractor.domain.guard import evaluate

pytestmark = pytest.mark.unit


def test_evaluate_simple_equality_true() -> None:
    """evaluate('status == "done"', ...) returns True when status equals 'done'."""
    assert evaluate('status == "done"', {"status": "done"}) is True


def test_evaluate_simple_equality_false() -> None:
    """evaluate('status == "done"', ...) returns False when status differs."""
    assert evaluate('status == "done"', {"status": "pending"}) is False


def test_evaluate_missing_key_is_falsy() -> None:
    """Evaluate with a missing key returns False (missing = falsy, not exception)."""
    assert evaluate("active", {}) is False


def test_evaluate_not_with_missing_key() -> None:
    """evaluate('not active', {}) returns True (not falsy = True)."""
    assert evaluate("not active", {}) is True


def test_evaluate_non_mapping_intermediate_is_falsy() -> None:
    """evaluate('a.b.c', {'a': 'string'}) returns False (non-mapping intermediate)."""
    assert evaluate("a.b.c", {"a": "string"}) is False


def test_evaluate_nested_key_access() -> None:
    """evaluate('ctx.status == "ok"', {'ctx': {'status': 'ok'}}) returns True."""
    assert evaluate('ctx.status == "ok"', {"ctx": {"status": "ok"}}) is True


def test_evaluate_guard_too_long_raises_validation_error() -> None:
    """A guard string longer than 512 chars raises PipelineValidationError at parse time."""
    long_guard = "a" * 513
    with pytest.raises(PipelineValidationError):
        _ = evaluate(long_guard, {})


def test_evaluate_excessive_nesting_depth_raises_validation_error() -> None:
    """A guard expression with parse-tree nesting depth > 32 raises PipelineValidationError.

    Each 'not ' prefix adds one level of parse-tree depth. 33 chained 'not's exceed
    the MAX_GUARD_DEPTH=32 limit.
    """
    deeply_nested = "not " * 33 + "true"
    with pytest.raises(PipelineValidationError):
        _ = evaluate(deeply_nested, {})


def test_evaluate_malformed_guard_raises_validation_error() -> None:
    """A malformed guard raises PipelineValidationError, not SyntaxError or ValueError."""
    with pytest.raises(PipelineValidationError):
        _ = evaluate("== bad syntax !!!", {})


def test_evaluate_unclosed_paren_raises_validation_error() -> None:
    """A guard with an unclosed parenthesis raises PipelineValidationError."""
    with pytest.raises(PipelineValidationError):
        _ = evaluate("(a == 1", {})


def test_evaluate_key_path_too_long_returns_false() -> None:
    """A dot-path with more than 4 segments returns False (total behavior)."""
    assert evaluate("a.b.c.d.e", {}) is False


def test_evaluate_numeric_comparison_less_than() -> None:
    """evaluate('count < 5', ...) returns True when count < 5."""
    assert evaluate("count < 5", {"count": 3}) is True


def test_evaluate_numeric_comparison_greater_than() -> None:
    """evaluate('count > 2', ...) returns True when count > 2."""
    assert evaluate("count > 2", {"count": 3}) is True


def test_evaluate_numeric_comparison_less_equal() -> None:
    """evaluate('count <= 3', ...) returns True when count <= 3."""
    assert evaluate("count <= 3", {"count": 3}) is True


def test_evaluate_numeric_comparison_greater_equal() -> None:
    """evaluate('count >= 3', ...) returns True when count >= 3."""
    assert evaluate("count >= 3", {"count": 3}) is True


def test_evaluate_numeric_comparison_not_equal() -> None:
    """evaluate('count != 5', ...) returns True when count != 5."""
    assert evaluate("count != 5", {"count": 3}) is True


def test_evaluate_type_mismatch_returns_false() -> None:
    """Comparing incompatible types (e.g. string < int) returns False (total)."""
    assert evaluate("status < 5", {"status": "done"}) is False


def test_evaluate_and_expression() -> None:
    """evaluate('a and b', ...) returns True only when both a and b are truthy."""
    assert evaluate("a and b", {"a": "yes", "b": "yes"}) is True
    assert evaluate("a and b", {"a": "yes", "b": ""}) is False


def test_evaluate_or_expression() -> None:
    """evaluate('a or b', ...) returns True when at least one is truthy."""
    assert evaluate("a or b", {"a": "", "b": "yes"}) is True
    assert evaluate("a or b", {"a": "", "b": ""}) is False


def test_evaluate_parenthesised_expression() -> None:
    """Evaluate with parentheses groups correctly."""
    assert evaluate("(a or b) and c", {"a": "yes", "b": "", "c": "yes"}) is True
    assert evaluate("(a or b) and c", {"a": "", "b": "", "c": "yes"}) is False


def test_evaluate_bool_literal_true() -> None:
    """evaluate('true', ...) returns True."""
    assert evaluate("true", {}) is True


def test_evaluate_bool_literal_false() -> None:
    """evaluate('false', ...) returns False."""
    assert evaluate("false", {}) is False


def test_evaluate_null_literal_is_falsy() -> None:
    """evaluate('null', ...) returns False (null is falsy)."""
    assert evaluate("null", {}) is False


def test_evaluate_string_literal_is_truthy() -> None:
    """evaluate('"hello"', ...) returns True (non-empty string is truthy)."""
    assert evaluate('"hello"', {}) is True


def test_evaluate_single_quoted_string() -> None:
    """Evaluate with single-quoted string works like double-quoted."""
    assert evaluate("status == 'done'", {"status": "done"}) is True


def test_evaluate_number_literal_is_truthy() -> None:
    """evaluate('42', ...) returns True (non-zero number is truthy)."""
    assert evaluate("42", {}) is True


def test_evaluate_extra_tokens_raise_validation_error() -> None:
    """A guard with trailing tokens after a valid expression raises PipelineValidationError."""
    with pytest.raises(PipelineValidationError):
        _ = evaluate("true false", {})


def test_evaluate_trailing_comparison_op_raises_validation_error() -> None:
    """A guard ending with a comparison operator raises PipelineValidationError."""
    with pytest.raises(PipelineValidationError):
        _ = evaluate("a ==", {})


def test_evaluate_double_comparison_op_raises_validation_error() -> None:
    """A guard with consecutive comparison operators raises PipelineValidationError."""
    with pytest.raises(PipelineValidationError):
        _ = evaluate("a == ==", {})
