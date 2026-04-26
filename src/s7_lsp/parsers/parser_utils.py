"""Shared helpers for parser source ranges and diagnostics."""

from __future__ import annotations

from collections.abc import Callable

from lark import Tree, UnexpectedCharacters, UnexpectedToken
from lark.exceptions import UnexpectedInput

from s7_lsp.ast_nodes import Diagnostic, Position, Range


def tree_range(node: Tree) -> Range:
    """Extract a zero-based source range from a Lark tree node."""
    start_line = getattr(node.meta, "line", 1) - 1
    start_col = getattr(node.meta, "column", 1) - 1
    end_line = getattr(node.meta, "end_line", start_line + 1) - 1
    end_col = getattr(node.meta, "end_column", start_col + 1) - 1

    return Range(
        start=Position(line=max(0, start_line), character=max(0, start_col)),
        end=Position(line=max(0, end_line), character=max(0, end_col)),
    )


def unexpected_char_diagnostic(e: UnexpectedCharacters) -> Diagnostic:
    """Convert Lark UnexpectedCharacters to a parser diagnostic."""
    line = (e.line or 1) - 1
    col = (e.column or 1) - 1
    char = e.char if hasattr(e, "char") and e.char else "?"

    return Diagnostic(
        message=f"Unexpected character: '{char}'",
        range=Range(
            start=Position(line=line, character=col),
            end=Position(line=line, character=col + 1),
        ),
        severity=1,
    )


def unexpected_token_diagnostic(
    e: UnexpectedToken,
    clean_expected: Callable[[set[str]], list[str]] | None = None,
) -> Diagnostic:
    """Convert Lark UnexpectedToken to a parser diagnostic."""
    line = (e.line or 1) - 1
    col = (e.column or 1) - 1
    token = str(e.token) if e.token else "?"

    expected = ""
    if e.expected and clean_expected is not None:
        clean = clean_expected(e.expected)
        if clean:
            expected = f" (expected: {', '.join(sorted(clean)[:5])})"

    return Diagnostic(
        message=f"Unexpected token: '{token}'{expected}",
        range=Range(
            start=Position(line=line, character=col),
            end=Position(line=line, character=col + len(token)),
        ),
        severity=1,
    )


def generic_parse_diagnostic(e: UnexpectedInput) -> Diagnostic:
    """Convert Lark UnexpectedInput to a parser diagnostic."""
    line = (getattr(e, "line", 1) or 1) - 1
    col = (getattr(e, "column", 1) or 1) - 1

    return Diagnostic(
        message=f"Syntax error: {e}",
        range=Range(
            start=Position(line=line, character=col),
            end=Position(line=line, character=col + 1),
        ),
        severity=1,
    )
