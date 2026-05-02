"""Tests for parser edge cases not covered elsewhere."""

from __future__ import annotations

from s7_lsp.parsers.awl_parser import parse_awl
from s7_lsp.parsers.resource_parser import parse_resource
from s7_lsp.parsers.scl_parser import parse_scl

_AWL_URI = "file:///test/sample.awl"


# ---------------------------------------------------------------------------
# AWL parser - unsupported diagnostic
# ---------------------------------------------------------------------------


def test_awl_returns_informational_diagnostic():
    """parse_awl() must emit exactly one diagnostic with severity 3 (Information)."""
    doc = parse_awl("// some awl content", _AWL_URI)
    assert len(doc.diagnostics) == 1
    diag = doc.diagnostics[0]
    assert diag.severity == 3, f"Expected severity 3 (Information), got {diag.severity}"


def test_awl_diagnostic_mentions_awl():
    """Diagnostic message should name the unsupported language clearly."""
    doc = parse_awl("", _AWL_URI)
    assert "AWL" in doc.diagnostics[0].message or "awl" in doc.diagnostics[0].message.lower()


def test_awl_returns_empty_blocks():
    """parse_awl() should return no blocks (stub behaviour unchanged)."""
    doc = parse_awl("", _AWL_URI)
    assert doc.blocks == []


def test_awl_preserves_uri():
    """parse_awl() must echo back the uri passed in."""
    doc = parse_awl("", _AWL_URI)
    assert doc.uri == _AWL_URI


# ---------------------------------------------------------------------------
# Exception sanitization - no internal details in user-facing message
# ---------------------------------------------------------------------------


def test_scl_generic_error_message_does_not_contain_exception_text(monkeypatch):
    """The catch-all diagnostic must not expose raw exception strings."""
    import s7_lsp.parsers.scl_parser as _mod

    def _bad_parser():
        class _P:
            def parse(self, src):
                raise RuntimeError("secret internal path: C:\\dev\\s7-lsp\\secret.py")

        return _P()

    monkeypatch.setattr(_mod, "_get_parser", _bad_parser)
    doc = parse_scl("FUNCTION_BLOCK FB1 END_FUNCTION_BLOCK", "file:///x.scl")
    error_diags = [d for d in doc.diagnostics if d.severity == 1]
    assert error_diags, "Expected at least one Error diagnostic from catch-all"
    for d in error_diags:
        assert "secret" not in d.message, f"Exception detail leaked into message: {d.message!r}"
        assert "C:\\" not in d.message, f"File path leaked into message: {d.message!r}"


def test_resource_generic_error_message_does_not_contain_exception_text(monkeypatch):
    """The catch-all diagnostic in resource_parser must not expose raw exception strings."""
    import s7_lsp.parsers.resource_parser as _mod

    def _bad_parser():
        class _P:
            def parse(self, src):
                raise RuntimeError("secret internal path: C:\\dev\\s7-lsp\\secret.py")

        return _P()

    monkeypatch.setattr(_mod, "_get_parser", _bad_parser)
    doc = parse_resource("key = value", "file:///x.s7res")
    error_diags = [d for d in doc.diagnostics if d.severity == 1]
    assert error_diags, "Expected at least one Error diagnostic from catch-all"
    for d in error_diags:
        assert "secret" not in d.message, f"Exception detail leaked into message: {d.message!r}"
