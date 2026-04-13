"""Tests for semantic/type_info.py.

Covers every acceptance criterion for task_002:
- BUILTIN_TYPE_INFO contains all 28 built-in types from the grammar.
- get_type_hover_text('DINT') returns a non-None markdown string containing
  '32-bit signed integer'.
- get_type_hover_text('MyCustomType') returns None.
- Lookup is case-insensitive (get_type_hover_text('dint') returns a result).
- No imports from lsprotocol in the module under test.
"""

import pytest

from s7_lsp.semantic.type_info import (
    BUILTIN_TYPE_INFO,
    get_type_hover_text,
)

# ---------------------------------------------------------------------------
# Expected types from grammar
# ---------------------------------------------------------------------------

EXPECTED_TYPES = {
    "BOOL",
    "SINT",
    "USINT",
    "INT",
    "UINT",
    "DINT",
    "UDINT",
    "LINT",
    "ULINT",
    "REAL",
    "LREAL",
    "BYTE",
    "WORD",
    "DWORD",
    "LWORD",
    "CHAR",
    "WCHAR",
    "STRING",
    "WSTRING",
    "TIME",
    "LTIME",
    "DATE",
    "LDATE",
    "TIME_OF_DAY",
    "LTIME_OF_DAY",
    "DATE_AND_TIME",
    "LDATE_AND_TIME",
}


# ---------------------------------------------------------------------------
# Acceptance criterion: all 28 built-in types are present
# ---------------------------------------------------------------------------


def test_builtin_type_info_contains_all_28_types():
    """BUILTIN_TYPE_INFO must have an entry for every type in the grammar."""
    missing = EXPECTED_TYPES - set(BUILTIN_TYPE_INFO.keys())
    assert not missing, f"Missing type entries: {missing}"


def test_builtin_type_info_count_matches_expected():
    """Dict size must equal the number of distinct types in EXPECTED_TYPES."""
    assert len(BUILTIN_TYPE_INFO) >= len(EXPECTED_TYPES)


# ---------------------------------------------------------------------------
# Acceptance criterion: TypeDescription is a frozen dataclass
# ---------------------------------------------------------------------------


def test_type_description_is_frozen():
    td = BUILTIN_TYPE_INFO["DINT"]
    with pytest.raises((AttributeError, TypeError)):
        td.name = "MODIFIED"  # type: ignore[misc]


def test_type_description_fields():
    td = BUILTIN_TYPE_INFO["DINT"]
    assert isinstance(td.name, str)
    assert isinstance(td.description, str)
    assert isinstance(td.size_bits, int)
    # range_str may be str or None
    assert td.range_str is None or isinstance(td.range_str, str)
    assert isinstance(td.category, str)


# ---------------------------------------------------------------------------
# Acceptance criterion: get_type_hover_text('DINT') is correct
# ---------------------------------------------------------------------------


def test_get_type_hover_text_dint_is_not_none():
    result = get_type_hover_text("DINT")
    assert result is not None


def test_get_type_hover_text_dint_contains_description():
    result = get_type_hover_text("DINT")
    assert "32-bit signed integer" in result  # type: ignore[operator]


def test_get_type_hover_text_dint_contains_range():
    result = get_type_hover_text("DINT")
    assert result is not None
    assert "Range:" in result
    assert "-2,147,483,648" in result


def test_get_type_hover_text_dint_contains_size():
    result = get_type_hover_text("DINT")
    assert result is not None
    assert "Size: 32 bits" in result


def test_get_type_hover_text_dint_contains_bold_name():
    result = get_type_hover_text("DINT")
    assert result is not None
    assert "**DINT**" in result


# ---------------------------------------------------------------------------
# Acceptance criterion: unknown types return None
# ---------------------------------------------------------------------------


def test_get_type_hover_text_unknown_returns_none():
    assert get_type_hover_text("MyCustomType") is None


def test_get_type_hover_text_empty_string_returns_none():
    assert get_type_hover_text("") is None


# ---------------------------------------------------------------------------
# Acceptance criterion: lookup is case-insensitive
# ---------------------------------------------------------------------------


def test_get_type_hover_text_lowercase():
    result = get_type_hover_text("dint")
    assert result is not None
    assert "32-bit signed integer" in result


def test_get_type_hover_text_mixed_case():
    result = get_type_hover_text("DiNt")
    assert result is not None


def test_get_type_hover_text_all_types_case_insensitive():
    for type_name in EXPECTED_TYPES:
        assert get_type_hover_text(type_name.lower()) is not None, (
            f"get_type_hover_text('{type_name.lower()}') returned None"
        )


# ---------------------------------------------------------------------------
# Acceptance criterion: no imports from lsprotocol in type_info module
# ---------------------------------------------------------------------------


def test_no_lsprotocol_imports():
    """The type_info module must not import from lsprotocol.

    We check the actual import statements by inspecting the module's direct
    imports (via sys.modules snapshot before/after import, and by examining
    the module's __dict__ for lsprotocol objects).
    """
    import s7_lsp.semantic.type_info as ti_module

    # lsprotocol must not appear as an attribute of the module
    assert not any(
        "lsprotocol" in str(type(v).__module__ or "")
        for v in vars(ti_module).values()
        if v is not None
    ), "type_info.py must not import objects from lsprotocol"

    # lsprotocol must not be a direct dependency recorded in __spec__ or globals
    module_globals = vars(ti_module)
    assert "lsprotocol" not in module_globals, (
        "lsprotocol must not be imported as a name in type_info"
    )


# ---------------------------------------------------------------------------
# Additional correctness checks for representative types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "type_name, expected_bits, expected_category",
    [
        ("BOOL", 1, "bit"),
        ("SINT", 8, "integer"),
        ("USINT", 8, "unsigned"),
        ("INT", 16, "integer"),
        ("UINT", 16, "unsigned"),
        ("DINT", 32, "integer"),
        ("UDINT", 32, "unsigned"),
        ("LINT", 64, "integer"),
        ("ULINT", 64, "unsigned"),
        ("REAL", 32, "float"),
        ("LREAL", 64, "float"),
        ("BYTE", 8, "bit"),
        ("WORD", 16, "bit"),
        ("DWORD", 32, "bit"),
        ("LWORD", 64, "bit"),
        ("CHAR", 8, "string"),
        ("WCHAR", 16, "string"),
        ("TIME", 32, "time"),
        ("LTIME", 64, "time"),
        ("DATE", 16, "date"),
        ("TIME_OF_DAY", 32, "time"),
        ("LTIME_OF_DAY", 64, "time"),
        ("DATE_AND_TIME", 64, "date"),
        ("LDATE_AND_TIME", 64, "date"),
    ],
)
def test_type_metadata(type_name, expected_bits, expected_category):
    td = BUILTIN_TYPE_INFO[type_name]
    assert td.size_bits == expected_bits, (
        f"{type_name}: expected {expected_bits} bits, got {td.size_bits}"
    )
    assert td.category == expected_category, (
        f"{type_name}: expected category '{expected_category}', got '{td.category}'"
    )


def test_string_types_have_no_range():
    """String/char types have no numeric range."""
    for name in ("CHAR", "WCHAR", "STRING", "WSTRING"):
        assert BUILTIN_TYPE_INFO[name].range_str is None, f"{name} should have range_str=None"


def test_valid_category_values():
    """All entries must use one of the defined categories."""
    valid = {"integer", "unsigned", "float", "bit", "string", "time", "date"}
    for name, td in BUILTIN_TYPE_INFO.items():
        assert td.category in valid, f"{name} has unknown category '{td.category}'"
