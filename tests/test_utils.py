"""Tests for src/s7_lsp/features/utils.py.

Covers every acceptance criterion:
- word_at_position: plain, #hash, "quoted" identifiers
- word_at_position: returns None on whitespace/operator
- word_at_position: member access chain extraction
- get_context: AFTER_DOT, AFTER_HASH, INSIDE_QUOTES, INSIDE_CALL,
               TYPE_POSITION, GENERAL
- get_context: nested parentheses handled correctly for INSIDE_CALL
- All functions are pure (verified structurally — no lsprotocol imports)
"""

import importlib.util
import types

import pytest

from s7_lsp.features.utils import (
    ContextKind,
    WordInfo,
    get_context,
    word_at_position,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def src(*lines: str) -> str:
    """Join lines with newline for use as multi-line source text."""
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Purity check — no lsprotocol / ast_nodes imports in utils
# ---------------------------------------------------------------------------


def test_utils_has_no_forbidden_imports():
    """utils.py must not import from lsprotocol, ast_nodes, or any project module."""
    spec = importlib.util.find_spec("s7_lsp.features.utils")
    assert spec is not None
    import s7_lsp.features.utils as mod

    # Walk the module's globals for any imported module objects
    forbidden_prefixes = ("lsprotocol", "s7_lsp.ast_nodes", "s7_lsp.semantic", "s7_lsp.parsers")
    for _name, obj in vars(mod).items():
        if isinstance(obj, types.ModuleType):
            module_name = obj.__name__
            for prefix in forbidden_prefixes:
                assert not module_name.startswith(prefix), (
                    f"utils.py imports forbidden module: {module_name}"
                )


# ---------------------------------------------------------------------------
# word_at_position — plain identifiers
# ---------------------------------------------------------------------------


class TestWordAtPositionPlain:
    def test_simple_word_start(self):
        source = "myVar := 0;"
        # cursor at start of 'myVar'
        info = word_at_position(source, 0, 0)
        assert info is not None
        assert info.word == "myVar"
        assert info.prefix == ""
        assert info.start_char == 0
        assert info.end_char == 5

    def test_simple_word_middle(self):
        source = "myVar := 0;"
        info = word_at_position(source, 0, 2)  # cursor on 'V'
        assert info is not None
        assert info.word == "myVar"

    def test_simple_word_end(self):
        source = "myVar := 0;"
        info = word_at_position(source, 0, 4)  # cursor on 'r'
        assert info is not None
        assert info.word == "myVar"

    def test_underscore_identifier(self):
        source = "_my_var_1 := TRUE;"
        info = word_at_position(source, 0, 0)
        assert info is not None
        assert info.word == "_my_var_1"

    def test_multiline_second_line(self):
        source = src("x := 1;", "result := x + 2;")
        info = word_at_position(source, 1, 0)  # cursor on 'result'
        assert info is not None
        assert info.word == "result"
        assert info.start_line == 1

    def test_range_values(self):
        source = "  speed := 0;"
        info = word_at_position(source, 0, 2)  # cursor on 's'
        assert info is not None
        assert info.start_char == 2
        assert info.end_char == 7  # 'speed' is 5 chars

    def test_chain_single_plain(self):
        source = "myVar := 0;"
        info = word_at_position(source, 0, 0)
        assert info is not None
        assert info.chain == ["myVar"]


# ---------------------------------------------------------------------------
# word_at_position — hash-prefixed identifiers
# ---------------------------------------------------------------------------


class TestWordAtPositionHash:
    def test_cursor_on_hash(self):
        source = "#localVar := 0;"
        info = word_at_position(source, 0, 0)  # cursor on '#'
        assert info is not None
        assert info.word == "localVar"
        assert info.prefix == "#"
        assert info.start_char == 0

    def test_cursor_on_ident_after_hash(self):
        source = "#localVar := 0;"
        info = word_at_position(source, 0, 1)  # cursor on 'l'
        assert info is not None
        assert info.word == "localVar"
        assert info.prefix == "#"
        assert info.start_char == 0

    def test_cursor_in_middle_of_hash_ident(self):
        source = "#motorSpeed := 0;"
        info = word_at_position(source, 0, 5)  # cursor on 'r' in 'motor'
        assert info is not None
        assert info.word == "motorSpeed"
        assert info.prefix == "#"

    def test_hash_chain_is_prefixed(self):
        source = "#localVar := 0;"
        info = word_at_position(source, 0, 1)
        assert info is not None
        assert info.chain == ["#localVar"]

    def test_hash_end_char(self):
        source = "#x := 0;"
        info = word_at_position(source, 0, 0)
        assert info is not None
        assert info.end_char == 2  # '#x'


# ---------------------------------------------------------------------------
# word_at_position — quoted identifiers
# ---------------------------------------------------------------------------


class TestWordAtPositionQuoted:
    def test_cursor_on_opening_quote(self):
        source = '"GlobalDB".field'
        info = word_at_position(source, 0, 0)  # cursor on opening '"'
        assert info is not None
        assert info.word == "GlobalDB"
        assert info.prefix == '"'

    def test_cursor_inside_quoted(self):
        source = '"GlobalDB".field'
        info = word_at_position(source, 0, 3)  # cursor on 'b' inside quotes
        assert info is not None
        assert info.word == "GlobalDB"
        assert info.prefix == '"'

    def test_cursor_on_closing_quote(self):
        # closing quote is at index 9 in '"GlobalDB"'
        source = '"GlobalDB".field'
        # index 9 is the closing '"'
        info = word_at_position(source, 0, 9)
        # Either returns the quoted word or the field — depends on position
        # The closing '"' is still part of the quoted token
        assert info is not None

    def test_quoted_chain(self):
        source = '"GlobalDB"'
        info = word_at_position(source, 0, 1)
        assert info is not None
        assert info.chain == ['"GlobalDB"']

    def test_quoted_range(self):
        source = '"MyDB"'
        info = word_at_position(source, 0, 0)
        assert info is not None
        assert info.start_char == 0
        assert info.end_char == 6  # includes both quotes


# ---------------------------------------------------------------------------
# word_at_position — None on whitespace / operators
# ---------------------------------------------------------------------------


class TestWordAtPositionNone:
    def test_whitespace(self):
        source = "myVar := 0;"
        info = word_at_position(source, 0, 5)  # space after 'myVar'
        assert info is None

    def test_operator_colon_equals(self):
        source = "myVar := 0;"
        info = word_at_position(source, 0, 6)  # ':' of ':='
        assert info is None

    def test_semicolon(self):
        source = "x := 1;"
        info = word_at_position(source, 0, 6)  # ';'
        assert info is None

    def test_empty_line(self):
        source = src("", "x := 1;")
        info = word_at_position(source, 0, 0)
        assert info is None

    def test_out_of_range_line(self):
        source = "x := 1;"
        info = word_at_position(source, 99, 0)
        assert info is None

    def test_past_end_of_line(self):
        source = "x := 1;"
        info = word_at_position(source, 0, 100)
        assert info is None

    def test_plus_operator(self):
        source = "a + b"
        info = word_at_position(source, 0, 2)  # '+'
        assert info is None


# ---------------------------------------------------------------------------
# word_at_position — member access chains
# ---------------------------------------------------------------------------


class TestWordAtPositionChain:
    def test_hash_struct_dot_field_cursor_on_field(self):
        source = "#struct.field"
        # cursor on 'f' in 'field', index 8
        info = word_at_position(source, 0, 8)
        assert info is not None
        assert info.word == "field"
        assert "#struct" in info.chain
        assert "field" in info.chain
        assert info.chain == ["#struct", "field"]

    def test_hash_struct_dot_field_cursor_on_struct(self):
        source = "#struct.field"
        # cursor on '#' or 's' in '#struct'
        info = word_at_position(source, 0, 1)
        assert info is not None
        assert info.word == "struct"
        assert info.prefix == "#"

    def test_quoted_db_dot_field(self):
        source = '"MyDB".speed'
        # cursor on 's' in 'speed', index 7
        info = word_at_position(source, 0, 7)
        assert info is not None
        assert info.word == "speed"
        assert info.chain == ['"MyDB"', "speed"]

    def test_three_level_chain(self):
        source = "#a.b.c"
        # cursor on 'c'
        info = word_at_position(source, 0, 5)
        assert info is not None
        assert info.word == "c"
        assert info.chain == ["#a", "b", "c"]

    def test_plain_dot_field(self):
        source = "myStruct.myField"
        info = word_at_position(source, 0, 10)  # cursor on 'm' in 'myField'
        assert info is not None
        assert info.word == "myField"
        assert info.chain == ["myStruct", "myField"]


# ---------------------------------------------------------------------------
# get_context — AFTER_DOT
# ---------------------------------------------------------------------------


class TestGetContextAfterDot:
    def test_after_dot(self):
        source = "#struct."
        ctx = get_context(source, 0, 8)  # cursor right after '.'
        assert ctx == ContextKind.AFTER_DOT

    def test_after_dot_with_partial_word(self):
        # Even when user has typed a partial word after '.', the context
        # is still useful. This tests the scanner on text up to the cursor.
        source = "#struct.fi"
        # We pass the position right after '.' (col 8); the partial 'fi' is not
        # yet typed from the scanner's perspective.
        ctx = get_context(source, 0, 8)
        assert ctx == ContextKind.AFTER_DOT

    def test_after_dot_whitespace_before_cursor(self):
        # If there's whitespace between '.' and cursor we don't expect AFTER_DOT
        # because get_context skips whitespace. Test confirms behaviour.
        source = "#s. "
        ctx = get_context(source, 0, 4)
        # Skipping whitespace backwards finds '.', so AFTER_DOT is expected.
        assert ctx == ContextKind.AFTER_DOT


# ---------------------------------------------------------------------------
# get_context — AFTER_HASH
# ---------------------------------------------------------------------------


class TestGetContextAfterHash:
    def test_after_hash(self):
        source = "#"
        ctx = get_context(source, 0, 1)
        assert ctx == ContextKind.AFTER_HASH

    def test_after_hash_in_expression(self):
        source = "x := #"
        ctx = get_context(source, 0, 6)
        assert ctx == ContextKind.AFTER_HASH


# ---------------------------------------------------------------------------
# get_context — INSIDE_QUOTES
# ---------------------------------------------------------------------------


class TestGetContextInsideQuotes:
    def test_inside_quotes(self):
        source = '"'
        ctx = get_context(source, 0, 1)
        assert ctx == ContextKind.INSIDE_QUOTES

    def test_inside_quotes_with_partial_name(self):
        source = '"My'
        ctx = get_context(source, 0, 3)
        assert ctx == ContextKind.INSIDE_QUOTES

    def test_outside_closed_quotes(self):
        # After closing quote we are NOT inside quotes
        source = '"MyDB".'
        ctx = get_context(source, 0, 7)
        assert ctx == ContextKind.AFTER_DOT


# ---------------------------------------------------------------------------
# get_context — INSIDE_CALL
# ---------------------------------------------------------------------------


class TestGetContextInsideCall:
    def test_inside_call_simple(self):
        source = "MyFC("
        ctx = get_context(source, 0, 5)
        assert ctx == ContextKind.INSIDE_CALL

    def test_inside_call_with_partial_arg(self):
        source = "MyFC(speed"
        ctx = get_context(source, 0, 10)
        assert ctx == ContextKind.INSIDE_CALL

    def test_nested_parens_outer_call(self):
        # Inside outer call, nested parens balanced
        source = "MyFC(nested(a, b), "
        ctx = get_context(source, 0, 19)
        assert ctx == ContextKind.INSIDE_CALL

    def test_nested_parens_inner_call(self):
        # Inside both outer and inner call
        source = "MyFC(nested("
        ctx = get_context(source, 0, 12)
        assert ctx == ContextKind.INSIDE_CALL

    def test_after_closed_paren_not_inside_call(self):
        source = "MyFC(a)"
        ctx = get_context(source, 0, 7)
        # After the closing paren, not inside the call
        assert ctx != ContextKind.INSIDE_CALL

    def test_balanced_nested_parens_leaves_outer(self):
        # "MyFC( (inner) , " — cursor after comma, still inside outer call
        source = "MyFC( (inner), "
        ctx = get_context(source, 0, 15)
        assert ctx == ContextKind.INSIDE_CALL


# ---------------------------------------------------------------------------
# get_context — TYPE_POSITION
# ---------------------------------------------------------------------------


class TestGetContextTypePosition:
    def test_type_position_after_colon(self):
        source = "myVar : "
        ctx = get_context(source, 0, 8)  # cursor after ': '
        assert ctx == ContextKind.TYPE_POSITION

    def test_type_position_no_space(self):
        source = "myVar :"
        ctx = get_context(source, 0, 7)
        assert ctx == ContextKind.TYPE_POSITION

    def test_not_type_position_assignment(self):
        source = "myVar := "
        ctx = get_context(source, 0, 9)
        # ':=' is assignment, not type separator
        assert ctx != ContextKind.TYPE_POSITION

    def test_type_position_with_partial_type(self):
        source = "myVar : INT"
        # cursor right after ':'
        ctx = get_context(source, 0, 7)
        assert ctx == ContextKind.TYPE_POSITION


# ---------------------------------------------------------------------------
# get_context — GENERAL
# ---------------------------------------------------------------------------


class TestGetContextGeneral:
    def test_empty_source(self):
        ctx = get_context("", 0, 0)
        assert ctx == ContextKind.GENERAL

    def test_start_of_line(self):
        source = "IF "
        ctx = get_context(source, 0, 0)
        assert ctx == ContextKind.GENERAL

    def test_after_keyword(self):
        source = "IF "
        ctx = get_context(source, 0, 3)
        # After 'IF ', not after any special char
        assert ctx == ContextKind.GENERAL

    def test_after_semicolon(self):
        source = "x := 1; "
        ctx = get_context(source, 0, 8)
        assert ctx == ContextKind.GENERAL


# ---------------------------------------------------------------------------
# ContextKind enum completeness
# ---------------------------------------------------------------------------


def test_context_kind_has_all_values():
    expected = {
        "AFTER_DOT",
        "AFTER_HASH",
        "INSIDE_QUOTES",
        "INSIDE_CALL",
        "TYPE_POSITION",
        "GENERAL",
    }
    actual = {member.name for member in ContextKind}
    assert expected == actual


# ---------------------------------------------------------------------------
# WordInfo dataclass is frozen
# ---------------------------------------------------------------------------


def test_word_info_is_frozen():
    info = WordInfo(
        word="test",
        prefix="",
        start_line=0,
        start_char=0,
        end_line=0,
        end_char=4,
        chain=["test"],
    )
    with pytest.raises((AttributeError, TypeError)):
        info.word = "changed"  # type: ignore[misc]
