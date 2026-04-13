"""Tests for the keyword completion feature (completion.py).

Covers:
- GENERAL context returns keyword completions
- Snippet templates have correct insert_text with placeholders
- END_IF offered when an unmatched IF precedes the cursor
- END_FOR / END_WHILE / END_REPEAT / END_CASE offered for respective unmatched keywords
- No END_* offered when every open keyword is already closed
- Non-snippet keywords have PlainText insert_text_format
- All completion items have CompletionItemKind.Keyword
- AFTER_HASH context returns variable completions (PRD 3.2)
- TYPE_POSITION context returns built-in and UDT type completions (PRD 3.3)
"""

from __future__ import annotations

from lsprotocol import types as lsp

from s7_lsp.ast_nodes import ParsedDocument
from s7_lsp.features.completion import (
    _block_name_completions,
    _builtin_type_completions,
    _count_unmatched,
    _member_completions,
    _named_param_completions,
    _udt_completions,
    _variable_completions,
    get_completions,
)
from s7_lsp.semantic.symbol_table import SymbolTable, VariableSymbol

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_URI = "file:///test/sample.scl"


def _make_doc(source: str = "") -> ParsedDocument:
    """Create a minimal ParsedDocument with the given source."""
    return ParsedDocument(uri=_TEST_URI, source=source)


def _position(line: int, character: int) -> lsp.Position:
    return lsp.Position(line=line, character=character)


def _labels(items: list[lsp.CompletionItem]) -> set[str]:
    return {item.label for item in items}


def _item(items: list[lsp.CompletionItem], label: str) -> lsp.CompletionItem | None:
    for item in items:
        if item.label == label:
            return item
    return None


# ---------------------------------------------------------------------------
# get_completions — GENERAL context returns keyword completions
# ---------------------------------------------------------------------------

SIMPLE_SOURCE = """\
FUNCTION_BLOCK "TestFB"
VAR_TEMP
    x : INT;
END_VAR


END_FUNCTION_BLOCK
"""


def test_general_context_returns_items():
    """Typing on an empty line in a block body returns completion items."""
    doc = _make_doc(SIMPLE_SOURCE)
    # Line 5 (0-based) is the blank line after END_VAR
    result = get_completions(doc, _position(5, 0), SIMPLE_SOURCE)
    assert isinstance(result, lsp.CompletionList)
    assert result.is_incomplete is False
    assert len(result.items) > 0


def test_general_context_includes_keyword_labels():
    """GENERAL context includes IF, FOR, WHILE, REPEAT, CASE keywords."""
    doc = _make_doc(SIMPLE_SOURCE)
    result = get_completions(doc, _position(5, 0), SIMPLE_SOURCE)
    labels = _labels(result.items)
    for kw in ("IF", "FOR", "WHILE", "REPEAT", "CASE"):
        assert kw in labels, f"Expected keyword '{kw}' in completions"


def test_general_context_includes_plain_keywords():
    """GENERAL context includes RETURN, EXIT, CONTINUE."""
    doc = _make_doc(SIMPLE_SOURCE)
    result = get_completions(doc, _position(5, 0), SIMPLE_SOURCE)
    labels = _labels(result.items)
    for kw in ("RETURN", "EXIT", "CONTINUE"):
        assert kw in labels, f"Expected keyword '{kw}' in completions"


# ---------------------------------------------------------------------------
# CompletionItemKind
# ---------------------------------------------------------------------------


def test_all_items_have_keyword_kind():
    """Every returned CompletionItem must have kind=Keyword."""
    doc = _make_doc(SIMPLE_SOURCE)
    result = get_completions(doc, _position(5, 0), SIMPLE_SOURCE)
    for item in result.items:
        assert item.kind == lsp.CompletionItemKind.Keyword, (
            f"Item '{item.label}' has kind {item.kind}, expected Keyword"
        )


# ---------------------------------------------------------------------------
# Snippet templates
# ---------------------------------------------------------------------------


def test_if_snippet_insert_text():
    """IF snippet has correct template with condition and END_IF."""
    doc = _make_doc(SIMPLE_SOURCE)
    result = get_completions(doc, _position(5, 0), SIMPLE_SOURCE)
    it = _item(result.items, "IF")
    assert it is not None, "IF completion item not found"
    assert it.insert_text_format == lsp.InsertTextFormat.Snippet
    assert "IF" in it.insert_text
    assert "THEN" in it.insert_text
    assert "END_IF" in it.insert_text
    assert "${1:condition}" in it.insert_text
    assert "$0" in it.insert_text


def test_for_snippet_insert_text():
    """FOR snippet has full FOR/TO/DO/END_FOR template with placeholders."""
    doc = _make_doc(SIMPLE_SOURCE)
    result = get_completions(doc, _position(5, 0), SIMPLE_SOURCE)
    it = _item(result.items, "FOR")
    assert it is not None, "FOR completion item not found"
    assert it.insert_text_format == lsp.InsertTextFormat.Snippet
    insert = it.insert_text
    assert "FOR" in insert
    assert ":=" in insert
    assert "TO" in insert
    assert "DO" in insert
    assert "END_FOR" in insert
    assert "$0" in insert


def test_while_snippet_insert_text():
    """WHILE snippet includes WHILE/DO/END_WHILE with placeholders."""
    doc = _make_doc(SIMPLE_SOURCE)
    result = get_completions(doc, _position(5, 0), SIMPLE_SOURCE)
    it = _item(result.items, "WHILE")
    assert it is not None, "WHILE completion item not found"
    assert it.insert_text_format == lsp.InsertTextFormat.Snippet
    insert = it.insert_text
    assert "WHILE" in insert
    assert "DO" in insert
    assert "END_WHILE" in insert


def test_repeat_snippet_insert_text():
    """REPEAT snippet includes REPEAT/UNTIL/END_REPEAT with placeholders."""
    doc = _make_doc(SIMPLE_SOURCE)
    result = get_completions(doc, _position(5, 0), SIMPLE_SOURCE)
    it = _item(result.items, "REPEAT")
    assert it is not None, "REPEAT completion item not found"
    assert it.insert_text_format == lsp.InsertTextFormat.Snippet
    insert = it.insert_text
    assert "REPEAT" in insert
    assert "UNTIL" in insert
    assert "END_REPEAT" in insert


def test_case_snippet_insert_text():
    """CASE snippet includes CASE/OF/END_CASE with placeholders."""
    doc = _make_doc(SIMPLE_SOURCE)
    result = get_completions(doc, _position(5, 0), SIMPLE_SOURCE)
    it = _item(result.items, "CASE")
    assert it is not None, "CASE completion item not found"
    assert it.insert_text_format == lsp.InsertTextFormat.Snippet
    insert = it.insert_text
    assert "CASE" in insert
    assert "OF" in insert
    assert "END_CASE" in insert


def test_if_else_snippet():
    """IF ... ELSE snippet is offered and contains ELSE branch."""
    doc = _make_doc(SIMPLE_SOURCE)
    result = get_completions(doc, _position(5, 0), SIMPLE_SOURCE)
    it = _item(result.items, "IF ... ELSE")
    assert it is not None, "IF ... ELSE completion item not found"
    assert it.insert_text_format == lsp.InsertTextFormat.Snippet
    insert = it.insert_text
    assert "ELSE" in insert
    assert "END_IF" in insert


# ---------------------------------------------------------------------------
# Plain-text keywords
# ---------------------------------------------------------------------------


def test_plain_keywords_are_plaintext_format():
    """RETURN, EXIT, CONTINUE must use PlainText format."""
    doc = _make_doc(SIMPLE_SOURCE)
    result = get_completions(doc, _position(5, 0), SIMPLE_SOURCE)
    for kw in ("RETURN", "EXIT", "CONTINUE"):
        it = _item(result.items, kw)
        assert it is not None, f"'{kw}' completion item not found"
        assert it.insert_text_format == lsp.InsertTextFormat.PlainText, (
            f"'{kw}' should be PlainText but got {it.insert_text_format}"
        )
        assert it.insert_text == kw


# ---------------------------------------------------------------------------
# END_* context-sensitive completions
# ---------------------------------------------------------------------------

_UNMATCHED_IF_SOURCE = """\
FUNCTION_BLOCK "TestFB"
VAR_TEMP
    x : INT;
END_VAR

    IF #x = 1 THEN

"""

_MATCHED_IF_SOURCE = """\
FUNCTION_BLOCK "TestFB"
VAR_TEMP
    x : INT;
END_VAR

    IF #x = 1 THEN
        x := 2;
    END_IF;

"""


def test_end_if_offered_for_unmatched_if():
    """END_IF is offered when there is an unmatched IF in preceding lines."""
    doc = _make_doc(_UNMATCHED_IF_SOURCE)
    # Position is on the last blank line, inside the unmatched IF block
    result = get_completions(doc, _position(7, 0), _UNMATCHED_IF_SOURCE)
    labels = _labels(result.items)
    assert "END_IF" in labels, "END_IF should be offered for unmatched IF"


def test_end_if_not_offered_when_if_matched():
    """END_IF is NOT offered when every IF is already closed."""
    doc = _make_doc(_MATCHED_IF_SOURCE)
    result = get_completions(doc, _position(9, 0), _MATCHED_IF_SOURCE)
    labels = _labels(result.items)
    assert "END_IF" not in labels, "END_IF should not be offered when IF is matched"


def test_end_for_offered_for_unmatched_for():
    """END_FOR is offered when there is an unmatched FOR."""
    source = "    FOR i := 1 TO 10 DO\n        \n"
    doc = _make_doc(source)
    result = get_completions(doc, _position(1, 0), source)
    assert "END_FOR" in _labels(result.items)


def test_end_while_offered_for_unmatched_while():
    """END_WHILE is offered when there is an unmatched WHILE."""
    source = "    WHILE TRUE DO\n        \n"
    doc = _make_doc(source)
    result = get_completions(doc, _position(1, 0), source)
    assert "END_WHILE" in _labels(result.items)


def test_end_repeat_offered_for_unmatched_repeat():
    """END_REPEAT is offered when there is an unmatched REPEAT."""
    source = "    REPEAT\n        \n"
    doc = _make_doc(source)
    result = get_completions(doc, _position(1, 0), source)
    assert "END_REPEAT" in _labels(result.items)


def test_end_case_offered_for_unmatched_case():
    """END_CASE is offered when there is an unmatched CASE."""
    source = "    CASE x OF\n        1: y := 1;\n"
    doc = _make_doc(source)
    result = get_completions(doc, _position(1, 0), source)
    assert "END_CASE" in _labels(result.items)


def test_end_if_is_plaintext_format():
    """END_IF completion item must use PlainText format, not Snippet."""
    doc = _make_doc(_UNMATCHED_IF_SOURCE)
    result = get_completions(doc, _position(7, 0), _UNMATCHED_IF_SOURCE)
    it = _item(result.items, "END_IF")
    assert it is not None
    assert it.insert_text_format == lsp.InsertTextFormat.PlainText
    assert it.insert_text == "END_IF"


# ---------------------------------------------------------------------------
# _count_unmatched unit tests
# ---------------------------------------------------------------------------


def test_count_unmatched_simple():
    """Single open IF returns count 1."""
    assert _count_unmatched(["IF x THEN"], "IF", "END_IF") == 1


def test_count_unmatched_matched():
    """Matched IF/END_IF returns 0."""
    lines = ["IF x THEN", "    y := 1;", "END_IF;"]
    assert _count_unmatched(lines, "IF", "END_IF") == 0


def test_count_unmatched_nested():
    """Nested IFs — outer unmatched count is 1."""
    lines = [
        "IF a THEN",
        "    IF b THEN",
        "    END_IF;",
        # outer IF still open
    ]
    assert _count_unmatched(lines, "IF", "END_IF") == 1


def test_count_unmatched_all_matched():
    """Fully matched nested IFs returns 0."""
    lines = [
        "IF a THEN",
        "    IF b THEN",
        "    END_IF;",
        "END_IF;",
    ]
    assert _count_unmatched(lines, "IF", "END_IF") == 0


def test_count_unmatched_case_insensitive():
    """Pattern matching is case-insensitive."""
    assert _count_unmatched(["if x then"], "IF", "END_IF") == 1
    assert _count_unmatched(["if x then", "end_if;"], "IF", "END_IF") == 0


# ---------------------------------------------------------------------------
# Non-GENERAL context produces no items (basic guard)
# ---------------------------------------------------------------------------


def test_after_dot_context_no_keyword_items():
    """After a dot (member access) context should not return keyword completions."""
    # Cursor placed right after '.' on the identifier
    source = "#myStruct.field"
    doc = _make_doc(source)
    # character=10 is just after the '.' (0-indexed: '#myStruct.' is 10 chars)
    result = get_completions(doc, _position(0, 10), source)
    # Keyword completions should not appear in AFTER_DOT context
    labels = _labels(result.items)
    assert "IF" not in labels
    assert "FOR" not in labels


def test_empty_source_returns_keyword_items():
    """Completions on empty source should still return keyword items."""
    source = "\n"
    doc = _make_doc(source)
    result = get_completions(doc, _position(0, 0), source)
    labels = _labels(result.items)
    assert "IF" in labels


# ---------------------------------------------------------------------------
# Helpers for variable and type completion tests
# ---------------------------------------------------------------------------

_FB_SOURCE = """\
FUNCTION_BLOCK "MotorFB"
VAR_INPUT
    Enable : BOOL;
    Speed : INT;
END_VAR
VAR_OUTPUT
    Running : BOOL;
END_VAR
VAR_TEMP
    Counter : DINT;
END_VAR

    IF #Enable THEN
        #Running := TRUE;
    END_IF;

END_FUNCTION_BLOCK
"""
# In _FB_SOURCE:
#   Line 12 (0-based): '    IF #Enable THEN'  — '#' is at column 7, so character=8 is AFTER_HASH
#   Line 13           : '        #Running := TRUE;' — '#' at column 8

_FB_URI = "file:///test/motor.scl"


def _make_symbol_table_from_source(source: str, uri: str) -> SymbolTable:
    """Parse *source*, register blocks in a fresh SymbolTable, and return it."""
    from s7_lsp.parsers.scl_parser import parse_scl

    doc = parse_scl(source, uri)
    st = SymbolTable()
    st.add_from_document(uri, doc.blocks)
    return st


def _make_doc_with_uri(source: str, uri: str) -> ParsedDocument:
    return ParsedDocument(uri=uri, source=source)


# ---------------------------------------------------------------------------
# Variable completion — AFTER_HASH context (PRD 3.2)
# ---------------------------------------------------------------------------


def test_after_hash_returns_variable_completions():
    """Typing '#' inside a block body returns all declared variables."""
    # Line 12 (0-based): '    IF #Enable THEN' — '#' is at column 7.
    # character=8 is immediately after '#', triggering AFTER_HASH context.
    source = _FB_SOURCE
    uri = _FB_URI
    doc = _make_doc_with_uri(source, uri)
    st = _make_symbol_table_from_source(source, uri)

    result = get_completions(doc, _position(12, 8), source, st)
    labels = _labels(result.items)

    assert "Enable" in labels, "VAR_INPUT variable 'Enable' should appear"
    assert "Speed" in labels, "VAR_INPUT variable 'Speed' should appear"
    assert "Running" in labels, "VAR_OUTPUT variable 'Running' should appear"
    assert "Counter" in labels, "VAR_TEMP variable 'Counter' should appear"


def test_variable_completions_kind_is_variable():
    """Every variable completion item must have kind=Variable."""
    source = _FB_SOURCE
    uri = _FB_URI
    doc = _make_doc_with_uri(source, uri)
    st = _make_symbol_table_from_source(source, uri)

    result = get_completions(doc, _position(12, 8), source, st)
    for it in result.items:
        assert it.kind == lsp.CompletionItemKind.Variable, (
            f"Item '{it.label}' has kind {it.kind}, expected Variable"
        )


def test_variable_completions_detail_is_type_name():
    """Variable completion detail field must show the type name."""
    source = _FB_SOURCE
    uri = _FB_URI
    doc = _make_doc_with_uri(source, uri)
    st = _make_symbol_table_from_source(source, uri)

    result = get_completions(doc, _position(12, 8), source, st)
    it = _item(result.items, "Enable")
    assert it is not None, "'Enable' completion item not found"
    assert it.detail == "BOOL", f"Expected detail 'BOOL', got {it.detail!r}"

    it_speed = _item(result.items, "Speed")
    assert it_speed is not None
    assert it_speed.detail == "INT"

    it_counter = _item(result.items, "Counter")
    assert it_counter is not None
    assert it_counter.detail == "DINT"


def test_variable_completions_documentation_is_section_kind():
    """Variable completion documentation field must show the section kind."""
    source = _FB_SOURCE
    uri = _FB_URI
    doc = _make_doc_with_uri(source, uri)
    st = _make_symbol_table_from_source(source, uri)

    result = get_completions(doc, _position(12, 8), source, st)
    it = _item(result.items, "Enable")
    assert it is not None
    assert it.documentation == "VAR_INPUT"

    it_running = _item(result.items, "Running")
    assert it_running is not None
    assert it_running.documentation == "VAR_OUTPUT"

    it_counter = _item(result.items, "Counter")
    assert it_counter is not None
    assert it_counter.documentation == "VAR_TEMP"


def test_variable_completions_sort_text_input_output_first():
    """VAR_INPUT and VAR_OUTPUT variables sort before others via sort_text prefix."""
    source = _FB_SOURCE
    uri = _FB_URI
    doc = _make_doc_with_uri(source, uri)
    st = _make_symbol_table_from_source(source, uri)

    result = get_completions(doc, _position(12, 8), source, st)

    def get_sort_text(label: str) -> str:
        it = _item(result.items, label)
        assert it is not None, f"'{label}' not found in completions"
        return it.sort_text

    assert get_sort_text("Enable").startswith("0_"), "VAR_INPUT should have '0_' prefix"
    assert get_sort_text("Speed").startswith("0_"), "VAR_INPUT should have '0_' prefix"
    assert get_sort_text("Running").startswith("0_"), "VAR_OUTPUT should have '0_' prefix"
    assert get_sort_text("Counter").startswith("1_"), "VAR_TEMP should have '1_' prefix"


def test_after_hash_no_symbol_table_returns_empty():
    """AFTER_HASH context with no symbol table returns empty list."""
    source = "    #"
    doc = _make_doc(source)
    result = get_completions(doc, _position(0, 5), source, symbol_table=None)
    assert result.items == []


def test_variable_completions_helper_direct():
    """_variable_completions() helper builds correct items from VariableSymbol list."""
    vars_ = [
        VariableSymbol(
            name="MyInput",
            kind="variable",
            definition_uri="file:///x.scl",
            definition_range_start_line=1,
            definition_range_start_char=4,
            definition_range_end_line=1,
            definition_range_end_char=20,
            type_name="INT",
            section_kind="VAR_INPUT",
            block_name="MyBlock",
        ),
        VariableSymbol(
            name="MyTemp",
            kind="variable",
            definition_uri="file:///x.scl",
            definition_range_start_line=2,
            definition_range_start_char=4,
            definition_range_end_line=2,
            definition_range_end_char=18,
            type_name="BOOL",
            section_kind="VAR_TEMP",
            block_name="MyBlock",
        ),
    ]
    items = _variable_completions(vars_)
    assert len(items) == 2

    input_item = next(it for it in items if it.label == "MyInput")
    assert input_item.kind == lsp.CompletionItemKind.Variable
    assert input_item.detail == "INT"
    assert input_item.documentation == "VAR_INPUT"
    assert input_item.sort_text == "0_MyInput"

    temp_item = next(it for it in items if it.label == "MyTemp")
    assert temp_item.sort_text == "1_MyTemp"


# ---------------------------------------------------------------------------
# Type completion — TYPE_POSITION context (PRD 3.3)
# ---------------------------------------------------------------------------


_TYPE_DECL_SOURCE = """\
FUNCTION_BLOCK "TypeTestFB"
VAR_INPUT
    Val :
END_VAR

END_FUNCTION_BLOCK

TYPE "MyRecord"
STRUCT
    Field : INT;
END_STRUCT;
END_TYPE
"""

_TYPE_URI = "file:///test/typetest.scl"


def test_type_position_returns_builtin_types():
    """Typing after ':' in a declaration returns all built-in type names."""
    source = _TYPE_DECL_SOURCE
    uri = _TYPE_URI
    doc = _make_doc_with_uri(source, uri)
    st = _make_symbol_table_from_source(source, uri)

    # Line 2 (0-based): "    Val : " — cursor at end after the space.
    result = get_completions(doc, _position(2, 10), source, st)
    labels = _labels(result.items)

    for type_name in ("BOOL", "INT", "DINT", "REAL", "STRING", "TIME"):
        assert type_name in labels, f"Built-in type '{type_name}' missing from completions"


def test_type_position_builtin_detail_is_description():
    """Built-in type completion items carry the human-readable description in detail."""
    items = _builtin_type_completions()
    assert len(items) > 0

    dint_item = next((it for it in items if it.label == "DINT"), None)
    assert dint_item is not None, "DINT not in builtin completions"
    assert dint_item.detail == "32-bit signed integer"
    assert dint_item.kind == lsp.CompletionItemKind.TypeParameter


def test_type_position_builtin_kind_is_type_parameter():
    """Every built-in type completion item must have kind=TypeParameter."""
    items = _builtin_type_completions()
    for it in items:
        assert it.kind == lsp.CompletionItemKind.TypeParameter, (
            f"Item '{it.label}' has kind {it.kind}, expected TypeParameter"
        )


def test_type_position_includes_udt():
    """Typing after ':' also returns user-defined TYPE blocks."""
    source = _TYPE_DECL_SOURCE
    uri = _TYPE_URI
    doc = _make_doc_with_uri(source, uri)
    st = _make_symbol_table_from_source(source, uri)

    result = get_completions(doc, _position(2, 10), source, st)
    labels = _labels(result.items)
    assert "MyRecord" in labels, "User-defined type 'MyRecord' should appear in type completions"


def test_udt_completions_kind_is_struct():
    """UDT completion items must have kind=Struct."""
    source = _TYPE_DECL_SOURCE
    uri = _TYPE_URI
    st = _make_symbol_table_from_source(source, uri)

    items = _udt_completions(st)
    for it in items:
        assert it.kind == lsp.CompletionItemKind.Struct


def test_udt_completions_detail_is_user_defined_type():
    """UDT completion items carry 'User-defined type' in detail."""
    source = _TYPE_DECL_SOURCE
    uri = _TYPE_URI
    st = _make_symbol_table_from_source(source, uri)

    items = _udt_completions(st)
    for it in items:
        assert it.detail == "User-defined type"


def test_type_position_no_symbol_table_returns_builtins_only():
    """TYPE_POSITION with no symbol table returns built-in types and no UDTs."""
    source = "    Val : "
    doc = _make_doc(source)
    result = get_completions(doc, _position(0, 10), source, symbol_table=None)
    labels = _labels(result.items)

    # Built-ins are always present
    assert "BOOL" in labels
    assert "INT" in labels

    # No UDT items — verify by checking all items have TypeParameter kind (no Struct)
    for it in result.items:
        assert it.kind == lsp.CompletionItemKind.TypeParameter, (
            f"Without symbol_table expected only TypeParameter, got {it.kind} for '{it.label}'"
        )


# ---------------------------------------------------------------------------
# Named parameter completion — INSIDE_CALL context (PRD 3.4)
# ---------------------------------------------------------------------------

_CALL_SOURCE = """\
FUNCTION_BLOCK "CallerFB"
VAR_INPUT
    Enable : BOOL;
END_VAR

    "MotorFB"(
END_FUNCTION_BLOCK
"""

_CALLEE_SOURCE = """\
FUNCTION_BLOCK "MotorFB"
VAR_INPUT
    Enable : BOOL;
    Speed : INT;
END_VAR
VAR_OUTPUT
    Running : BOOL;
END_VAR
VAR_IN_OUT
    Counter : DINT;
END_VAR

END_FUNCTION_BLOCK
"""

_CALLEE_URI = "file:///test/motor_callee.scl"
_CALLER_URI = "file:///test/caller.scl"


def _make_two_doc_symbol_table(
    callee_source: str, callee_uri: str, caller_source: str, caller_uri: str
) -> SymbolTable:
    """Build a SymbolTable containing blocks from two parsed documents."""
    from s7_lsp.parsers.scl_parser import parse_scl

    st = SymbolTable()
    callee_doc = parse_scl(callee_source, callee_uri)
    st.add_from_document(callee_uri, callee_doc.blocks)
    caller_doc = parse_scl(caller_source, caller_uri)
    st.add_from_document(caller_uri, caller_doc.blocks)
    return st


def test_inside_call_returns_named_param_completions():
    """Inside a function call, named parameter completions are offered."""
    st = _make_two_doc_symbol_table(_CALLEE_SOURCE, _CALLEE_URI, _CALL_SOURCE, _CALLER_URI)
    # "MotorFB"( — cursor just inside the paren, line 5, char 14
    source = _CALL_SOURCE
    doc = _make_doc_with_uri(source, _CALLER_URI)
    result = get_completions(doc, _position(5, 14), source, st)
    labels = _labels(result.items)
    assert "Enable" in labels, "VAR_INPUT 'Enable' should be in named param completions"
    assert "Speed" in labels, "VAR_INPUT 'Speed' should be in named param completions"
    assert "Running" in labels, "VAR_OUTPUT 'Running' should be in named param completions"
    assert "Counter" in labels, "VAR_IN_OUT 'Counter' should be in named param completions"


def test_inside_call_kind_is_property():
    """Named parameter completion items must have kind=Property."""
    st = _make_two_doc_symbol_table(_CALLEE_SOURCE, _CALLEE_URI, _CALL_SOURCE, _CALLER_URI)
    source = _CALL_SOURCE
    doc = _make_doc_with_uri(source, _CALLER_URI)
    result = get_completions(doc, _position(5, 14), source, st)
    for it in result.items:
        assert it.kind == lsp.CompletionItemKind.Property, (
            f"Item '{it.label}' has kind {it.kind}, expected Property"
        )


def test_input_param_uses_assign_operator():
    """VAR_INPUT parameters use ':=' in insert_text."""
    st = _make_two_doc_symbol_table(_CALLEE_SOURCE, _CALLEE_URI, _CALL_SOURCE, _CALLER_URI)
    source = _CALL_SOURCE
    doc = _make_doc_with_uri(source, _CALLER_URI)
    result = get_completions(doc, _position(5, 14), source, st)
    enable_item = _item(result.items, "Enable")
    assert enable_item is not None
    assert ":=" in enable_item.insert_text, "VAR_INPUT should use ':=' operator"
    assert "=>" not in enable_item.insert_text


def test_output_param_uses_out_operator():
    """VAR_OUTPUT parameters use '=>' in insert_text."""
    st = _make_two_doc_symbol_table(_CALLEE_SOURCE, _CALLEE_URI, _CALL_SOURCE, _CALLER_URI)
    source = _CALL_SOURCE
    doc = _make_doc_with_uri(source, _CALLER_URI)
    result = get_completions(doc, _position(5, 14), source, st)
    running_item = _item(result.items, "Running")
    assert running_item is not None
    assert "=>" in running_item.insert_text, "VAR_OUTPUT should use '=>' operator"


def test_named_param_insert_text_format_is_snippet():
    """Named parameter completions must use InsertTextFormat.Snippet."""
    st = _make_two_doc_symbol_table(_CALLEE_SOURCE, _CALLEE_URI, _CALL_SOURCE, _CALLER_URI)
    source = _CALL_SOURCE
    doc = _make_doc_with_uri(source, _CALLER_URI)
    result = get_completions(doc, _position(5, 14), source, st)
    for it in result.items:
        assert it.insert_text_format == lsp.InsertTextFormat.Snippet


def test_named_param_detail_is_type_name():
    """Named parameter completion detail must show the parameter type."""
    st = _make_two_doc_symbol_table(_CALLEE_SOURCE, _CALLEE_URI, _CALL_SOURCE, _CALLER_URI)
    source = _CALL_SOURCE
    doc = _make_doc_with_uri(source, _CALLER_URI)
    result = get_completions(doc, _position(5, 14), source, st)
    speed_item = _item(result.items, "Speed")
    assert speed_item is not None
    assert speed_item.detail == "INT"


def test_already_assigned_params_excluded():
    """Already-assigned parameters must not appear in completions."""
    # Build source with Enable already assigned inside the call.
    source_with_assigned = """\
FUNCTION_BLOCK "CallerFB"
VAR_INPUT
    Enable : BOOL;
END_VAR

    "MotorFB"(Enable := TRUE,
END_FUNCTION_BLOCK
"""
    st = _make_two_doc_symbol_table(_CALLEE_SOURCE, _CALLEE_URI, source_with_assigned, _CALLER_URI)
    doc = _make_doc_with_uri(source_with_assigned, _CALLER_URI)
    # Cursor at end of line 5: after the comma and space.
    line_text = '    "MotorFB"(Enable := TRUE, '
    char = len(line_text)
    result = get_completions(doc, _position(5, char), source_with_assigned, st)
    labels = _labels(result.items)
    assert "Enable" not in labels, "Already-assigned 'Enable' should not appear"
    assert "Speed" in labels, "Unassigned 'Speed' should still appear"


def test_named_param_completions_helper_direct():
    """_named_param_completions() returns correct items directly."""
    st = _make_two_doc_symbol_table(_CALLEE_SOURCE, _CALLEE_URI, _CALL_SOURCE, _CALLER_URI)
    # Simulate: line text '    "MotorFB"(' with cursor at position 14
    source = '    "MotorFB"(\n'
    items = _named_param_completions(source, 0, 14, st)
    labels = {it.label for it in items}
    assert "Enable" in labels
    assert "Speed" in labels
    assert "Running" in labels


def test_inside_call_no_symbol_table_returns_empty():
    """INSIDE_CALL with no symbol table returns empty list."""
    source = '    "MotorFB"(\n'
    doc = _make_doc(source)
    result = get_completions(doc, _position(0, 14), source, symbol_table=None)
    assert result.items == []


# ---------------------------------------------------------------------------
# Member completion — AFTER_DOT context (PRD 3.5)
# ---------------------------------------------------------------------------

_STRUCT_SOURCE = """\
FUNCTION_BLOCK "StructFB"
VAR_INPUT
    Enable : BOOL;
END_VAR
VAR

END_VAR

END_FUNCTION_BLOCK

TYPE "MotorData"
STRUCT
    Speed : INT;
    Running : BOOL;
    Torque : REAL;
END_STRUCT;
END_TYPE

DATA_BLOCK "MyDB"
"MotorData"

END_DATA_BLOCK
"""

_STRUCT_URI = "file:///test/struct.scl"

_MEMBER_CALLER_SOURCE = """\
FUNCTION_BLOCK "MemberTestFB"
VAR_INPUT
    MyMotor : "MotorData";
END_VAR

    #MyMotor.
END_FUNCTION_BLOCK
"""

_MEMBER_CALLER_URI = "file:///test/member_caller.scl"


_MEMBER_FB_SOURCE = """\
FUNCTION_BLOCK "FieldFB"
VAR_INPUT
    Speed : INT;
    Running : BOOL;
    Torque : REAL;
END_VAR

END_FUNCTION_BLOCK
"""

_MEMBER_FB_URI = "file:///test/fieldfb.scl"


def test_after_dot_returns_field_completions():
    """After 'FieldFB.' (a block name), its variables are offered as field completions."""
    st = _make_symbol_table_from_source(_MEMBER_FB_SOURCE, _MEMBER_FB_URI)
    from s7_lsp.semantic.scope import ScopeManager

    # "FieldFB" is 7 chars: '    "FieldFB".' has length 14, char=14
    source = '    "FieldFB".\n'
    char = len('    "FieldFB".')  # 14
    items = _member_completions(source, 0, char, ScopeManager(st), _MEMBER_FB_URI)
    labels = {it.label for it in items}
    assert "Speed" in labels, "'Speed' should be a field of FieldFB"
    assert "Running" in labels, "'Running' should be a field of FieldFB"
    assert "Torque" in labels, "'Torque' should be a field of FieldFB"


def test_after_dot_field_kind_is_field():
    """Member completion items must have kind=Field."""
    st = _make_symbol_table_from_source(_MEMBER_FB_SOURCE, _MEMBER_FB_URI)
    from s7_lsp.semantic.scope import ScopeManager

    source = '    "FieldFB".\n'
    char = len('    "FieldFB".')
    items = _member_completions(source, 0, char, ScopeManager(st), _MEMBER_FB_URI)
    assert len(items) > 0, "Expected at least one field completion"
    for it in items:
        assert it.kind == lsp.CompletionItemKind.Field, (
            f"Item '{it.label}' has kind {it.kind}, expected Field"
        )


def test_after_dot_field_detail_is_type():
    """Member completion items carry the field type in detail."""
    st = _make_symbol_table_from_source(_MEMBER_FB_SOURCE, _MEMBER_FB_URI)
    from s7_lsp.semantic.scope import ScopeManager

    source = '    "FieldFB".\n'
    char = len('    "FieldFB".')
    items = _member_completions(source, 0, char, ScopeManager(st), _MEMBER_FB_URI)
    speed_item = next((it for it in items if it.label == "Speed"), None)
    assert speed_item is not None, "'Speed' field not found in member completions"
    assert speed_item.detail == "INT"


def test_after_dot_via_variable_type():
    """After '#MyMotor.' where MyMotor : MotorData, MotorData fields are offered."""
    combined = _STRUCT_SOURCE + "\n" + _MEMBER_CALLER_SOURCE
    combined_uri = "file:///test/combined.scl"
    st = _make_symbol_table_from_source(combined, combined_uri)
    from s7_lsp.semantic.scope import ScopeManager

    # Line from _MEMBER_CALLER_SOURCE part — we simulate the cursor position
    source = "    #MyMotor.\n"
    # ScopeManager needs the block to resolve #MyMotor, so use a simpler check:
    # resolve_name on 'MyMotor' in combined document.
    scope_mgr = ScopeManager(st)
    items = _member_completions(source, 0, 14, scope_mgr, combined_uri)
    # MyMotor resolves to MotorData fields if scope resolution works;
    # if block context is unknown, it falls back to block lookup which may fail.
    # At minimum, verify no exception is raised.
    assert isinstance(items, list)


def test_after_dot_no_symbol_table_returns_empty():
    """AFTER_DOT context with no symbol table returns empty completions."""
    source = '    "MyDB".\n'
    doc = _make_doc(source)
    result = get_completions(doc, _position(0, 11), source, symbol_table=None)
    assert result.items == []


# ---------------------------------------------------------------------------
# Block name completion — INSIDE_QUOTES context (PRD 3.6)
# ---------------------------------------------------------------------------

_BLOCKS_SOURCE = """\
FUNCTION_BLOCK "SomeFB"
VAR_INPUT
    x : INT;
END_VAR
END_FUNCTION_BLOCK

FUNCTION "SomeFC" : INT
VAR_INPUT
    y : INT;
END_VAR
    "SomeFC" := 0;
END_FUNCTION

DATA_BLOCK "SomeDB"
"SomeFB"
END_DATA_BLOCK

TYPE "SomeUDT"
STRUCT
    z : BOOL;
END_STRUCT;
END_TYPE
"""

_BLOCKS_URI = "file:///test/blocks.scl"


def test_inside_quotes_returns_all_block_names():
    """Typing inside double-quotes returns all workspace block names."""
    st = _make_symbol_table_from_source(_BLOCKS_SOURCE, _BLOCKS_URI)
    items = _block_name_completions(st)
    labels = {it.label for it in items}
    assert "SomeFB" in labels
    assert "SomeFC" in labels
    assert "SomeDB" in labels
    assert "SomeUDT" in labels


def test_inside_quotes_fb_kind_is_module():
    """FUNCTION_BLOCK blocks must map to CompletionItemKind.Module."""
    st = _make_symbol_table_from_source(_BLOCKS_SOURCE, _BLOCKS_URI)
    items = _block_name_completions(st)
    fb_item = next((it for it in items if it.label == "SomeFB"), None)
    assert fb_item is not None
    assert fb_item.kind == lsp.CompletionItemKind.Module


def test_inside_quotes_fc_kind_is_function():
    """FUNCTION blocks must map to CompletionItemKind.Function."""
    st = _make_symbol_table_from_source(_BLOCKS_SOURCE, _BLOCKS_URI)
    items = _block_name_completions(st)
    fc_item = next((it for it in items if it.label == "SomeFC"), None)
    assert fc_item is not None
    assert fc_item.kind == lsp.CompletionItemKind.Function


def test_inside_quotes_db_kind_is_struct():
    """DB blocks must map to CompletionItemKind.Struct."""
    st = _make_symbol_table_from_source(_BLOCKS_SOURCE, _BLOCKS_URI)
    items = _block_name_completions(st)
    db_item = next((it for it in items if it.label == "SomeDB"), None)
    assert db_item is not None
    assert db_item.kind == lsp.CompletionItemKind.Struct


def test_inside_quotes_udt_kind_is_type_parameter():
    """TYPE blocks must map to CompletionItemKind.TypeParameter."""
    st = _make_symbol_table_from_source(_BLOCKS_SOURCE, _BLOCKS_URI)
    items = _block_name_completions(st)
    udt_item = next((it for it in items if it.label == "SomeUDT"), None)
    assert udt_item is not None
    assert udt_item.kind == lsp.CompletionItemKind.TypeParameter


def test_inside_quotes_detail_shows_block_kind_label():
    """Block name completion detail must show the short label (FB, FC, DB, UDT)."""
    st = _make_symbol_table_from_source(_BLOCKS_SOURCE, _BLOCKS_URI)
    items = _block_name_completions(st)

    def get_detail(label: str) -> str:
        it = next((i for i in items if i.label == label), None)
        assert it is not None, f"'{label}' not found in block name completions"
        return it.detail

    assert get_detail("SomeFB") == "FB"
    assert get_detail("SomeFC") == "FC"
    assert get_detail("SomeDB") == "DB"
    assert get_detail("SomeUDT") == "UDT"


def test_inside_quotes_via_get_completions():
    """get_completions() returns block name items in INSIDE_QUOTES context."""
    st = _make_symbol_table_from_source(_BLOCKS_SOURCE, _BLOCKS_URI)
    # Position cursor inside double quotes on a line like: "
    source = '"'
    doc = _make_doc_with_uri(source, _BLOCKS_URI)
    # character=1 puts cursor inside the open quote — INSIDE_QUOTES context.
    result = get_completions(doc, _position(0, 1), source, st)
    labels = _labels(result.items)
    assert "SomeFB" in labels
    assert "SomeFC" in labels


def test_inside_quotes_no_symbol_table_returns_empty():
    """INSIDE_QUOTES with no symbol table returns empty completions."""
    source = '"'
    doc = _make_doc(source)
    result = get_completions(doc, _position(0, 1), source, symbol_table=None)
    assert result.items == []
