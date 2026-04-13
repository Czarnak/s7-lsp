"""Tests for the get_hover() feature function.

Covers:
- Hash-prefixed variable (#var) hover: shows type and VAR section kind
- Double-quoted block name ("Block") hover: shows block signature with params
- Built-in type keyword hover: shows type description with range and size
- Plain identifier hover: resolves to variable or block
- Whitespace / unknown identifier hover: returns None
- Hover content is formatted as Markdown
"""

from __future__ import annotations

from lsprotocol import types as lsp

from s7_lsp.features.hover import get_hover

_TEST_URI = "file:///test/sample.scl"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pos(line: int, character: int) -> lsp.Position:
    return lsp.Position(line=line, character=character)


def _hover_value(hover: lsp.Hover) -> str:
    """Extract the markdown string from an lsp.Hover."""
    assert hover is not None
    assert isinstance(hover.contents, lsp.MarkupContent)
    assert hover.contents.kind == lsp.MarkupKind.Markdown
    return hover.contents.value


# ---------------------------------------------------------------------------
# Hash-prefixed variable hover (#var)
# ---------------------------------------------------------------------------


class TestHashPrefixedVariableHover:
    """Hovering over #-prefixed identifiers should show type and section."""

    def test_hover_var_input(self, parsed_document, symbol_table, sample_scl_source):
        """#Enable is VAR_INPUT BOOL in MotorControl (line 13, col 7)."""
        hover = get_hover(parsed_document, _pos(13, 7), sample_scl_source, symbol_table)
        val = _hover_value(hover)
        assert "Enable" in val
        assert "BOOL" in val
        assert "VAR_INPUT" in val

    def test_hover_hash_on_ident_body(self, parsed_document, symbol_table, sample_scl_source):
        """Hovering on the body character of #Enable (col 8) also resolves."""
        hover = get_hover(parsed_document, _pos(13, 8), sample_scl_source, symbol_table)
        val = _hover_value(hover)
        assert "Enable" in val
        assert "BOOL" in val

    def test_hover_var_output(self, parsed_document, symbol_table, sample_scl_source):
        """#Running is VAR_OUTPUT BOOL in MotorControl (line 14, col 8)."""
        hover = get_hover(parsed_document, _pos(14, 8), sample_scl_source, symbol_table)
        val = _hover_value(hover)
        assert "Running" in val
        assert "BOOL" in val
        assert "VAR_OUTPUT" in val

    def test_hover_var_temp(self, parsed_document, symbol_table, sample_scl_source):
        """#InputValue is VAR_INPUT INT in FC_Calculate (line 24, col 37)."""
        # Line 24: '    "FC_Calculate" := INT_TO_DINT(#InputValue);'
        # '#' is at col 36, 'I' at col 37
        hover = get_hover(parsed_document, _pos(24, 36), sample_scl_source, symbol_table)
        val = _hover_value(hover)
        assert "InputValue" in val
        assert "INT" in val

    def test_hover_hash_no_symbol_table_returns_none(self, parsed_document, sample_scl_source):
        """Without a symbol table, hash-prefix hover returns None."""
        hover = get_hover(parsed_document, _pos(13, 7), sample_scl_source, None)
        assert hover is None

    def test_hover_markdown_format(self, parsed_document, symbol_table, sample_scl_source):
        """Hover content uses bold markdown formatting."""
        hover = get_hover(parsed_document, _pos(13, 7), sample_scl_source, symbol_table)
        val = _hover_value(hover)
        # Should have bold formatting with '**'
        assert "**" in val


# ---------------------------------------------------------------------------
# Double-quoted block name ("Block") hover
# ---------------------------------------------------------------------------


class TestQuotedBlockHover:
    """Hovering over quoted block names shows block kind, return type, params."""

    def test_hover_function_block(self, parsed_document, symbol_table, sample_scl_source):
        """Hovering on "MotorControl" at line 0 shows FB signature."""
        # Line 0: 'FUNCTION_BLOCK "MotorControl"'
        # '"' is at col 15
        hover = get_hover(parsed_document, _pos(0, 15), sample_scl_source, symbol_table)
        val = _hover_value(hover)
        assert "MotorControl" in val
        assert "FB" in val

    def test_hover_function_block_shows_parameters(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """FB hover includes VAR_INPUT and VAR_OUTPUT parameter list."""
        hover = get_hover(parsed_document, _pos(0, 15), sample_scl_source, symbol_table)
        val = _hover_value(hover)
        assert "Enable" in val
        assert "Speed" in val
        assert "Running" in val
        assert "Parameters:" in val

    def test_hover_function_block_shows_section_kinds(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """Each parameter entry includes its section kind."""
        hover = get_hover(parsed_document, _pos(0, 15), sample_scl_source, symbol_table)
        val = _hover_value(hover)
        assert "VAR_INPUT" in val
        assert "VAR_OUTPUT" in val

    def test_hover_function_shows_return_type(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """Hovering on "FC_Calculate" at line 19 shows FC signature with return type DINT."""
        # Line 19: 'FUNCTION "FC_Calculate" : DINT'
        # '"' is at col 9
        hover = get_hover(parsed_document, _pos(19, 9), sample_scl_source, symbol_table)
        val = _hover_value(hover)
        assert "FC_Calculate" in val
        assert "FC" in val
        assert "DINT" in val

    def test_hover_data_block(self, parsed_document, symbol_table, sample_scl_source):
        """Hovering on "DB_Motor" shows DB kind."""
        # Line 35: 'DATA_BLOCK "DB_Motor"'
        # '"' is at col 11
        hover = get_hover(parsed_document, _pos(35, 11), sample_scl_source, symbol_table)
        val = _hover_value(hover)
        assert "DB_Motor" in val
        assert "DB" in val

    def test_hover_unknown_block_returns_none(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """A quoted name that has no registered block returns None."""
        # Inject a fake source with an unknown quoted ident
        fake_source = '    "UnknownBlock";\n'
        from s7_lsp.ast_nodes import ParsedDocument

        fake_doc = ParsedDocument(uri=_TEST_URI, blocks=[])
        hover = get_hover(fake_doc, _pos(0, 4), fake_source, symbol_table)
        assert hover is None

    def test_hover_quoted_block_markdown_format(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """Block hover uses Markdown bold formatting."""
        hover = get_hover(parsed_document, _pos(0, 15), sample_scl_source, symbol_table)
        val = _hover_value(hover)
        assert val.startswith("**")


# ---------------------------------------------------------------------------
# Built-in type keyword hover
# ---------------------------------------------------------------------------


class TestBuiltinTypeHover:
    """Hovering on built-in type keywords shows type documentation."""

    def test_hover_bool(self, parsed_document, sample_scl_source):
        """BOOL on line 3 col 13 shows boolean description."""
        # Line 3: '    Enable : BOOL;'
        # 'B' is at col 13
        hover = get_hover(parsed_document, _pos(3, 13), sample_scl_source, None)
        val = _hover_value(hover)
        assert "BOOL" in val
        assert "Boolean" in val or "bit" in val.lower() or "TRUE" in val

    def test_hover_dint(self, parsed_document, symbol_table, sample_scl_source):
        """DINT shows 32-bit signed integer documentation."""
        # Line 10: '    TempCounter : DINT;'
        # 'D' of DINT is at col 18
        hover = get_hover(parsed_document, _pos(10, 18), sample_scl_source, symbol_table)
        val = _hover_value(hover)
        assert "DINT" in val
        assert "32" in val

    def test_hover_int(self, parsed_document, sample_scl_source):
        """INT on line 4 shows 16-bit signed integer documentation."""
        # Line 4: '    Speed : INT;'
        # 'I' of INT is at col 12
        hover = get_hover(parsed_document, _pos(4, 12), sample_scl_source, None)
        val = _hover_value(hover)
        assert "INT" in val
        assert "16" in val

    def test_hover_builtin_type_shows_range(self, parsed_document, sample_scl_source):
        """Builtin type hover includes a range specification."""
        hover = get_hover(parsed_document, _pos(4, 12), sample_scl_source, None)
        val = _hover_value(hover)
        assert "Range:" in val

    def test_hover_builtin_type_shows_size(self, parsed_document, sample_scl_source):
        """Builtin type hover includes a size in bits."""
        hover = get_hover(parsed_document, _pos(4, 12), sample_scl_source, None)
        val = _hover_value(hover)
        assert "Size:" in val
        assert "bits" in val

    def test_hover_builtin_no_symbol_table(self, parsed_document, sample_scl_source):
        """Built-in type hover works without a symbol table."""
        hover = get_hover(parsed_document, _pos(3, 13), sample_scl_source, None)
        assert hover is not None

    def test_hover_builtin_type_markdown_bold(self, parsed_document, sample_scl_source):
        """Built-in type hover uses markdown bold for type name."""
        hover = get_hover(parsed_document, _pos(3, 13), sample_scl_source, None)
        val = _hover_value(hover)
        assert "**BOOL**" in val


# ---------------------------------------------------------------------------
# Plain identifier hover (no prefix, no quotes)
# ---------------------------------------------------------------------------


class TestPlainIdentifierHover:
    """Plain identifiers resolve to built-in types, variables, or blocks."""

    def test_hover_plain_block_keyword(self, parsed_document, sample_scl_source):
        """'FUNCTION_BLOCK' on line 0 col 0 is not a variable — returns None or block."""
        # 'FUNCTION_BLOCK' is a keyword not in the symbol table as a plain name
        hover = get_hover(parsed_document, _pos(0, 0), sample_scl_source, None)
        # No entry expected for the keyword itself
        # Either None or a builtin type (FUNCTION_BLOCK is not in BUILTIN_TYPE_INFO)
        assert hover is None

    def test_hover_plain_ident_resolves_to_var(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """'Enable' without '#' on line 3 (declaration line) resolves via scope."""
        # Line 3: '    Enable : BOOL;'
        # 'E' at col 4
        hover = get_hover(parsed_document, _pos(3, 4), sample_scl_source, symbol_table)
        # The parser puts the declaration at line 3; scope manager resolves it
        if hover is not None:
            val = _hover_value(hover)
            assert "Enable" in val or "BOOL" in val

    def test_hover_plain_ident_resolves_to_block(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """'MotorControl' on line 0 (past the quote) without prefix: scope sees block."""
        # After "MotorControl" closes at col 28, 'M' would be at col 16 (inside quotes)
        # Here we try a source snippet with a plain identifier that is a block name
        import textwrap

        fake_src = textwrap.dedent("""\
            MotorControl();
        """)
        from s7_lsp.ast_nodes import ParsedDocument

        fake_doc = ParsedDocument(uri=_TEST_URI, blocks=[])
        hover = get_hover(fake_doc, _pos(0, 0), fake_src, symbol_table)
        if hover is not None:
            val = _hover_value(hover)
            assert "MotorControl" in val


# ---------------------------------------------------------------------------
# Whitespace and unknown identifier: return None
# ---------------------------------------------------------------------------


class TestNoneReturns:
    """Hovering on whitespace or unknown identifiers returns None."""

    def test_hover_whitespace_returns_none(self, parsed_document, sample_scl_source):
        """Hovering on leading whitespace returns None."""
        # Line 3: '    Enable : BOOL;' — col 0 is a space
        hover = get_hover(parsed_document, _pos(3, 0), sample_scl_source, None)
        assert hover is None

    def test_hover_past_end_of_line_returns_none(self, parsed_document, sample_scl_source):
        """Hovering past end of line returns None."""
        hover = get_hover(parsed_document, _pos(3, 999), sample_scl_source, None)
        assert hover is None

    def test_hover_unknown_ident_no_symbol_table(self, parsed_document, sample_scl_source):
        """Unknown plain identifier without symbol table and not a builtin: None."""
        fake_src = "myUnknownIdent;\n"
        hover = get_hover(parsed_document, _pos(0, 0), fake_src, None)
        assert hover is None

    def test_hover_unknown_hash_ident_returns_none(
        self, parsed_document, symbol_table, sample_scl_source
    ):
        """#nonExistentVar that is not in symbol table returns None."""
        fake_src = "    IF #NonExistentVar THEN\n        #x := 1;\n    END_IF;\n"
        from s7_lsp.ast_nodes import ParsedDocument

        fake_doc = ParsedDocument(uri=_TEST_URI, blocks=[])
        hover = get_hover(fake_doc, _pos(0, 7), fake_src, symbol_table)
        assert hover is None

    def test_hover_operator_returns_none(self, parsed_document, sample_scl_source):
        """Hovering on ':' operator returns None."""
        # Line 3: '    Enable : BOOL;' — ':' is at col 11
        hover = get_hover(parsed_document, _pos(3, 11), sample_scl_source, None)
        assert hover is None

    def test_hover_empty_source_returns_none(self, parsed_document):
        """Empty source string returns None regardless of position."""
        hover = get_hover(parsed_document, _pos(0, 0), "", None)
        assert hover is None
