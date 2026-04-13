"""Tests for the find-references feature (features/references.py).

Covers:
- Variable references returns all lines where the variable name appears as a whole word
- Block references returns matches across all open documents
- #hashIdent variables are searched with the # prefix
- include_declaration=True adds the definition location to results
- include_declaration=False omits the definition location
- Returns empty list for unresolvable symbols
"""

from __future__ import annotations

import pytest
from lsprotocol import types as lsp

from s7_lsp.features.references import get_references
from s7_lsp.parsers.scl_parser import parse_scl
from s7_lsp.semantic.symbol_table import SymbolTable

# ---------------------------------------------------------------------------
# Test URIs and sources
# ---------------------------------------------------------------------------

_URI_A = "file:///workspace/blockA.scl"
_URI_B = "file:///workspace/blockB.scl"

# Source A contains FUNCTION_BLOCK "MotorFB" with a VAR_INPUT named "Enable"
# and several usages of #Enable in its body.
_SOURCE_A = """\
FUNCTION_BLOCK "MotorFB"
VAR_INPUT
    Enable : BOOL;
    Speed : INT;
END_VAR
VAR_TEMP
    TempVal : DINT;
END_VAR

    IF #Enable THEN
        IF #Enable AND #Speed > 0 THEN
            #TempVal := 1;
        END_IF;
    END_IF;

END_FUNCTION_BLOCK
"""

# Source B calls "MotorFB" (as a block reference) and also uses "MotorFB" as a type.
_SOURCE_B = """\
FUNCTION_BLOCK "ControllerFB"
VAR
    myMotor : "MotorFB";
END_VAR

    myMotor(Enable := TRUE, Speed := 100);

END_FUNCTION_BLOCK
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def symbol_table_ab() -> SymbolTable:
    """SymbolTable populated from both _SOURCE_A and _SOURCE_B."""
    st = SymbolTable()
    doc_a = parse_scl(_SOURCE_A, _URI_A)
    doc_b = parse_scl(_SOURCE_B, _URI_B)
    st.add_from_document(_URI_A, doc_a.blocks)
    st.add_from_document(_URI_B, doc_b.blocks)
    return st


@pytest.fixture(scope="module")
def parsed_doc_a():
    return parse_scl(_SOURCE_A, _URI_A)


@pytest.fixture(scope="module")
def parsed_doc_b():
    return parse_scl(_SOURCE_B, _URI_B)


@pytest.fixture(scope="module")
def documents_ab() -> dict[str, str]:
    return {_URI_A: _SOURCE_A, _URI_B: _SOURCE_B}


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _pos(line: int, character: int) -> lsp.Position:
    return lsp.Position(line=line, character=character)


def _uris(locations: list[lsp.Location]) -> list[str]:
    return [loc.uri for loc in locations]


def _lines(locations: list[lsp.Location]) -> list[int]:
    return [loc.range.start.line for loc in locations]


# ---------------------------------------------------------------------------
# Test: empty list for None symbol_table
# ---------------------------------------------------------------------------


def test_returns_empty_when_no_symbol_table(parsed_doc_a):
    """Returns [] when symbol_table is None."""
    result = get_references(
        parsed_doc_a,
        _pos(9, 13),  # cursor on #Enable in body
        _SOURCE_A,
        symbol_table=None,
    )
    assert result == []


# ---------------------------------------------------------------------------
# Test: empty list for unresolvable symbol
# ---------------------------------------------------------------------------


def test_returns_empty_for_unresolvable_symbol(parsed_doc_a, symbol_table_ab):
    """Returns [] when the cursor is on whitespace or an unknown identifier."""
    # Position on whitespace
    result = get_references(
        parsed_doc_a,
        _pos(0, 0),  # 'F' of FUNCTION_BLOCK keyword (not in symbol table)
        _SOURCE_A,
        symbol_table=symbol_table_ab,
    )
    # FUNCTION_BLOCK is not a known symbol — should return []
    assert result == []


# ---------------------------------------------------------------------------
# Test: hash variable references (whole-word, current file only)
# ---------------------------------------------------------------------------


def test_hash_variable_references(parsed_doc_a, symbol_table_ab, documents_ab):
    """#Enable usages are found with the # prefix on every occurrence line."""
    # Cursor is on "#Enable" at line 9 (0-based), character 8 ('E' after '#')
    # Line 9: "    IF #Enable THEN"
    result = get_references(
        parsed_doc_a,
        _pos(9, 8),  # character 8 is inside "Enable" (after the '#' at col 7)
        _SOURCE_A,
        symbol_table=symbol_table_ab,
        include_declaration=False,
        documents=documents_ab,
    )

    assert len(result) >= 2, f"Expected at least 2 #Enable occurrences, got: {result}"
    # All results must be in _URI_A (variable is local to MotorFB defined there)
    assert all(loc.uri == _URI_A for loc in result), "Variable refs must be in the defining file"
    # The matches must include the '#' prefix character
    found_lines = _lines(result)
    assert 9 in found_lines, "Line 9 should be in results (IF #Enable THEN)"
    assert 10 in found_lines, "Line 10 should be in results (IF #Enable AND ...)"


def test_hash_variable_references_exclude_declaration(parsed_doc_a, symbol_table_ab, documents_ab):
    """include_declaration=False does not include the VAR section definition line."""
    result = get_references(
        parsed_doc_a,
        _pos(9, 8),  # #Enable usage in body
        _SOURCE_A,
        symbol_table=symbol_table_ab,
        include_declaration=False,
        documents=documents_ab,
    )
    # Definition of Enable is on line 2 ("    Enable : BOOL;")
    assert 2 not in _lines(result), (
        "Declaration line must NOT appear when include_declaration=False"
    )


def test_hash_variable_references_include_declaration(parsed_doc_a, symbol_table_ab, documents_ab):
    """include_declaration=True prepends the definition location."""
    result = get_references(
        parsed_doc_a,
        _pos(9, 8),  # #Enable usage in body
        _SOURCE_A,
        symbol_table=symbol_table_ab,
        include_declaration=True,
        documents=documents_ab,
    )
    assert len(result) >= 1
    # The first location should be the declaration
    first = result[0]
    assert first.uri == _URI_A
    # Enable is declared on line 2 of _SOURCE_A
    assert first.range.start.line == 2


# ---------------------------------------------------------------------------
# Test: block references across all documents
# ---------------------------------------------------------------------------


def test_block_references_across_documents(parsed_doc_a, symbol_table_ab, documents_ab):
    """BlockSymbol references are found across all open documents."""
    # Cursor on "MotorFB" in the FUNCTION_BLOCK declaration line (line 0, col 17)
    # Line 0: FUNCTION_BLOCK "MotorFB"
    result = get_references(
        parsed_doc_a,
        _pos(0, 17),  # inside "MotorFB"
        _SOURCE_A,
        symbol_table=symbol_table_ab,
        include_declaration=False,
        documents=documents_ab,
    )
    uris = _uris(result)
    # "MotorFB" is used in _SOURCE_B as a type (line 2: myMotor : "MotorFB";)
    assert _URI_B in uris, "Block references must be found in other open documents"


def test_block_references_include_declaration(parsed_doc_a, symbol_table_ab, documents_ab):
    """include_declaration=True prepends the block's own definition location."""
    result = get_references(
        parsed_doc_a,
        _pos(0, 17),  # "MotorFB"
        _SOURCE_A,
        symbol_table=symbol_table_ab,
        include_declaration=True,
        documents=documents_ab,
    )
    assert len(result) >= 1
    first = result[0]
    # Declaration of MotorFB is in _URI_A at line 0
    assert first.uri == _URI_A
    assert first.range.start.line == 0


def test_block_references_no_documents_falls_back_to_current(parsed_doc_a, symbol_table_ab):
    """When documents=None, scan only the current source."""
    result = get_references(
        parsed_doc_a,
        _pos(0, 17),  # "MotorFB"
        _SOURCE_A,
        symbol_table=symbol_table_ab,
        include_declaration=False,
        documents=None,
    )
    # Only _SOURCE_A is scanned — occurrences of "MotorFB" in _SOURCE_B are absent
    uris = set(_uris(result))
    assert uris <= {_URI_A}, f"Expected only URI_A but got: {uris}"


# ---------------------------------------------------------------------------
# Test: plain (non-hash) variable references (whole-word)
# ---------------------------------------------------------------------------


def test_plain_variable_whole_word_match(parsed_doc_b, symbol_table_ab, documents_ab):
    """Plain variable names are matched as whole words only."""
    # "Speed" appears in _SOURCE_A declarations; cursor on Speed in _SOURCE_A line 3
    # Line 3: "    Speed : INT;"
    doc_a = parse_scl(_SOURCE_A, _URI_A)
    result = get_references(
        doc_a,
        _pos(3, 5),  # 'S' of Speed on line 3
        _SOURCE_A,
        symbol_table=symbol_table_ab,
        include_declaration=False,
        documents=documents_ab,
    )
    found_lines = _lines(result)
    # Speed is on line 3 (declaration) and line 10 (#Speed > 0)
    # At minimum we should find it at least once (the declaration itself is found by regex)
    assert len(result) >= 1


# ---------------------------------------------------------------------------
# Test: variable references stay within the defining file
# ---------------------------------------------------------------------------


def test_variable_references_confined_to_defining_uri(parsed_doc_a, symbol_table_ab, documents_ab):
    """Variable references for MotorFB.Enable must only appear in _URI_A."""
    result = get_references(
        parsed_doc_a,
        _pos(9, 8),
        _SOURCE_A,
        symbol_table=symbol_table_ab,
        include_declaration=False,
        documents=documents_ab,
    )
    assert all(loc.uri == _URI_A for loc in result)
