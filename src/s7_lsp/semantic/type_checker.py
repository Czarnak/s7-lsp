"""Type checking and inference for SCL — STUB (Phase 2).

Will provide:
- Expression type inference
- Assignment compatibility checking
- Function parameter type validation
- Implicit conversion warnings (e.g., REAL assigned to INT)
"""

from __future__ import annotations


# S7 type compatibility matrix — which types can be assigned to which.
# Phase 2 will use this for diagnostics.
NUMERIC_TYPES = frozenset({
    "BOOL", "SINT", "USINT", "INT", "UINT",
    "DINT", "UDINT", "LINT", "ULINT", "REAL", "LREAL",
    "BYTE", "WORD", "DWORD", "LWORD",
})

TIME_TYPES = frozenset({
    "TIME", "LTIME", "TIME_OF_DAY", "LTIME_OF_DAY",
    "DATE", "LDATE", "DATE_AND_TIME", "LDATE_AND_TIME",
})

STRING_TYPES = frozenset({"CHAR", "WCHAR", "STRING", "WSTRING"})

ALL_BUILTIN_TYPES = NUMERIC_TYPES | TIME_TYPES | STRING_TYPES


def is_builtin_type(type_name: str) -> bool:
    """Check if a type name is a built-in S7 type."""
    return type_name.upper() in ALL_BUILTIN_TYPES
