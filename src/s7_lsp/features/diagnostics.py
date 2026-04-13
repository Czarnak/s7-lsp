"""Diagnostics provider — converts parsed diagnostics to LSP protocol format.

Phase 1: Syntax error diagnostics from the parser.
Phase 2: Semantic diagnostics (undeclared variables, type mismatches).
Phase 3: Style/convention warnings (naming, unused variables).
"""

from __future__ import annotations

from lsprotocol import types as lsp

from s7_lsp.ast_nodes import Diagnostic as AstDiagnostic
from s7_lsp.ast_nodes import ParsedDocument
from s7_lsp.semantic.semantic_diagnostics import get_semantic_diagnostics
from s7_lsp.semantic.symbol_table import SymbolTable

# Map our severity integers to LSP DiagnosticSeverity enum
_SEVERITY_MAP: dict[int, lsp.DiagnosticSeverity] = {
    1: lsp.DiagnosticSeverity.Error,
    2: lsp.DiagnosticSeverity.Warning,
    3: lsp.DiagnosticSeverity.Information,
    4: lsp.DiagnosticSeverity.Hint,
}


def get_diagnostics(
    document: ParsedDocument,
    symbol_table: SymbolTable | None = None,
) -> list[lsp.Diagnostic]:
    """Convert all diagnostics from a parsed document to LSP format.

    This is the main entry point called by the server after each
    document change. It collects diagnostics from:
    1. The parser (syntax errors)
    2. (Phase 2) Semantic analysis (type errors, undeclared symbols)
    """
    lsp_diagnostics: list[lsp.Diagnostic] = []

    for diag in document.diagnostics:
        lsp_diagnostics.append(_to_lsp_diagnostic(diag))

    # Only run semantic diagnostics when the parse succeeded (no Error diagnostics).
    has_parse_errors = any(d.severity == 1 for d in document.diagnostics)
    if not has_parse_errors and symbol_table is not None:
        for sem_diag in get_semantic_diagnostics(document, symbol_table):
            lsp_diagnostics.append(_to_lsp_diagnostic(sem_diag))

    return lsp_diagnostics


def _to_lsp_diagnostic(diag: AstDiagnostic) -> lsp.Diagnostic:
    """Convert a single AST diagnostic to LSP format."""
    return lsp.Diagnostic(
        range=lsp.Range(
            start=lsp.Position(
                line=diag.range.start.line,
                character=diag.range.start.character,
            ),
            end=lsp.Position(
                line=diag.range.end.line,
                character=diag.range.end.character,
            ),
        ),
        message=diag.message,
        severity=_SEVERITY_MAP.get(diag.severity, lsp.DiagnosticSeverity.Error),
        source=diag.source,
    )
