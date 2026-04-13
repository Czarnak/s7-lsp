"""Shared pytest fixtures for s7-lsp tests.

Provides:
- sample_scl_source: a complete, parseable SCL source string with FB, FC, TYPE, DB
- parsed_document: the ParsedDocument produced by parse_scl()
- symbol_table: a SymbolTable populated from the parsed document
- scope_manager: a ScopeManager wrapping the symbol table
"""

import pytest

from s7_lsp.parsers.scl_parser import parse_scl
from s7_lsp.semantic.scope import ScopeManager
from s7_lsp.semantic.symbol_table import SymbolTable

_TEST_URI = "file:///test/sample.scl"

# ─── Source fixture ───────────────────────────────────────────


@pytest.fixture(scope="session")
def sample_scl_source() -> str:
    """A complete SCL source string containing FB, FC, TYPE, and DB declarations.

    The source is valid SCL that the lark grammar can parse without errors.
    """
    return """\
FUNCTION_BLOCK "MotorControl"
{ S7_Optimized_Access := 'TRUE' }
VAR_INPUT
    Enable : BOOL;
    Speed : INT;
END_VAR
VAR_OUTPUT
    Running : BOOL;
END_VAR
VAR_TEMP
    TempCounter : DINT;
END_VAR

    IF #Enable THEN
        #Running := TRUE;
    END_IF;

END_FUNCTION_BLOCK

FUNCTION "FC_Calculate" : DINT
VAR_INPUT
    InputValue : INT;
END_VAR

    "FC_Calculate" := INT_TO_DINT(#InputValue);

END_FUNCTION

TYPE "MotorData"
STRUCT
    MaxSpeed : INT;
    IsRunning : BOOL;
END_STRUCT;
END_TYPE

DATA_BLOCK "DB_Motor"
{ S7_Optimized_Access := 'TRUE' }
VAR
    Speed : INT;
    Active : BOOL;
END_VAR
END_DATA_BLOCK
"""


# ─── Parsed document fixture ──────────────────────────────────


@pytest.fixture(scope="session")
def parsed_document(sample_scl_source: str):
    """ParsedDocument produced by parse_scl() from sample_scl_source.

    Asserts that at least one block was parsed (i.e. parsing succeeded).
    """
    doc = parse_scl(sample_scl_source, _TEST_URI)
    assert doc.blocks, (
        "sample_scl_source produced no blocks — source may have a syntax error. "
        f"Diagnostics: {doc.diagnostics}"
    )
    return doc


# ─── Symbol table fixture ─────────────────────────────────────


@pytest.fixture(scope="session")
def symbol_table(parsed_document):
    """SymbolTable populated with all blocks from parsed_document."""
    st = SymbolTable()
    st.add_from_document(_TEST_URI, parsed_document.blocks)
    return st


# ─── Scope manager fixture ────────────────────────────────────


@pytest.fixture(scope="session")
def scope_manager(symbol_table: SymbolTable) -> ScopeManager:
    """ScopeManager wrapping the populated symbol table."""
    return ScopeManager(symbol_table)
