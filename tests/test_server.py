"""Tests for LSP server registration and pull diagnostics."""

from __future__ import annotations

from collections.abc import Callable

from lsprotocol import types as lsp

from s7_lsp.server import create_server

_URI = "file:///workspace/clean.scl"
_CLEAN_SOURCE = """\
FUNCTION_BLOCK Test
VAR_INPUT
    Enable : BOOL;
END_VAR
END_FUNCTION_BLOCK
"""


def _feature(server, method: str) -> Callable:
    return server.protocol.fm.features[method]


def test_text_document_diagnostic_is_registered() -> None:
    server = create_server()

    assert lsp.TEXT_DOCUMENT_DIAGNOSTIC in server.protocol.fm.features


def test_pull_diagnostics_for_clean_document_returns_empty_full_report(monkeypatch) -> None:
    server = create_server()
    monkeypatch.setattr(server, "text_document_publish_diagnostics", lambda params: None)

    _feature(server, lsp.TEXT_DOCUMENT_DID_OPEN)(
        lsp.DidOpenTextDocumentParams(
            text_document=lsp.TextDocumentItem(
                uri=_URI,
                language_id="siemens-scl",
                version=1,
                text=_CLEAN_SOURCE,
            )
        )
    )

    result = _feature(server, lsp.TEXT_DOCUMENT_DIAGNOSTIC)(
        lsp.DocumentDiagnosticParams(text_document=lsp.TextDocumentIdentifier(uri=_URI))
    )

    assert isinstance(result, lsp.FullDocumentDiagnosticReport)
    assert result.kind == "full"
    assert result.items == []


def test_pull_diagnostics_for_unknown_document_returns_empty_full_report() -> None:
    server = create_server()

    result = _feature(server, lsp.TEXT_DOCUMENT_DIAGNOSTIC)(
        lsp.DocumentDiagnosticParams(
            text_document=lsp.TextDocumentIdentifier(uri="file:///workspace/missing.scl")
        )
    )

    assert isinstance(result, lsp.FullDocumentDiagnosticReport)
    assert result.kind == "full"
    assert result.items == []
