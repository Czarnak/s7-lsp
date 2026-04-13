"""Built-in S7 type descriptions for hover and completion.

Provides a static dictionary of all S7-1500 built-in type metadata and a
helper that formats a markdown hover string for a given type name.

No lsprotocol imports — this is a pure data module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TypeDescription:
    """Metadata for a single S7 built-in type."""

    name: str
    """Canonical type name (e.g. 'DINT')."""

    description: str
    """Human-readable description (e.g. '32-bit signed integer')."""

    size_bits: int
    """Storage size in bits."""

    range_str: str | None
    """Value range as a formatted string, or None for non-numeric types."""

    category: str
    """Type category: 'integer', 'unsigned', 'float', 'bit', 'string', 'time', 'date'."""


BUILTIN_TYPE_INFO: dict[str, TypeDescription] = {
    # ------------------------------------------------------------------ #
    # Bit / boolean
    # ------------------------------------------------------------------ #
    "BOOL": TypeDescription(
        name="BOOL",
        description="Boolean value (TRUE or FALSE)",
        size_bits=1,
        range_str="FALSE (0) or TRUE (1)",
        category="bit",
    ),
    # ------------------------------------------------------------------ #
    # Bit strings
    # ------------------------------------------------------------------ #
    "BYTE": TypeDescription(
        name="BYTE",
        description="8-bit bit string",
        size_bits=8,
        range_str="16#00 to 16#FF",
        category="bit",
    ),
    "WORD": TypeDescription(
        name="WORD",
        description="16-bit bit string",
        size_bits=16,
        range_str="16#0000 to 16#FFFF",
        category="bit",
    ),
    "DWORD": TypeDescription(
        name="DWORD",
        description="32-bit bit string",
        size_bits=32,
        range_str="16#00000000 to 16#FFFFFFFF",
        category="bit",
    ),
    "LWORD": TypeDescription(
        name="LWORD",
        description="64-bit bit string",
        size_bits=64,
        range_str="16#0000000000000000 to 16#FFFFFFFFFFFFFFFF",
        category="bit",
    ),
    # ------------------------------------------------------------------ #
    # Signed integers
    # ------------------------------------------------------------------ #
    "SINT": TypeDescription(
        name="SINT",
        description="8-bit signed integer",
        size_bits=8,
        range_str="-128 to 127",
        category="integer",
    ),
    "INT": TypeDescription(
        name="INT",
        description="16-bit signed integer",
        size_bits=16,
        range_str="-32,768 to 32,767",
        category="integer",
    ),
    "DINT": TypeDescription(
        name="DINT",
        description="32-bit signed integer",
        size_bits=32,
        range_str="-2,147,483,648 to 2,147,483,647",
        category="integer",
    ),
    "LINT": TypeDescription(
        name="LINT",
        description="64-bit signed integer",
        size_bits=64,
        range_str="-9,223,372,036,854,775,808 to 9,223,372,036,854,775,807",
        category="integer",
    ),
    # ------------------------------------------------------------------ #
    # Unsigned integers
    # ------------------------------------------------------------------ #
    "USINT": TypeDescription(
        name="USINT",
        description="8-bit unsigned integer",
        size_bits=8,
        range_str="0 to 255",
        category="unsigned",
    ),
    "UINT": TypeDescription(
        name="UINT",
        description="16-bit unsigned integer",
        size_bits=16,
        range_str="0 to 65,535",
        category="unsigned",
    ),
    "UDINT": TypeDescription(
        name="UDINT",
        description="32-bit unsigned integer",
        size_bits=32,
        range_str="0 to 4,294,967,295",
        category="unsigned",
    ),
    "ULINT": TypeDescription(
        name="ULINT",
        description="64-bit unsigned integer",
        size_bits=64,
        range_str="0 to 18,446,744,073,709,551,615",
        category="unsigned",
    ),
    # ------------------------------------------------------------------ #
    # Floating point
    # ------------------------------------------------------------------ #
    "REAL": TypeDescription(
        name="REAL",
        description="32-bit IEEE 754 floating-point number",
        size_bits=32,
        range_str="-3.402823e+38 to 3.402823e+38",
        category="float",
    ),
    "LREAL": TypeDescription(
        name="LREAL",
        description="64-bit IEEE 754 double-precision floating-point number",
        size_bits=64,
        range_str="-1.7976931348623158e+308 to 1.7976931348623158e+308",
        category="float",
    ),
    # ------------------------------------------------------------------ #
    # Character / string
    # ------------------------------------------------------------------ #
    "CHAR": TypeDescription(
        name="CHAR",
        description="Single ASCII character (1 byte)",
        size_bits=8,
        range_str=None,
        category="string",
    ),
    "WCHAR": TypeDescription(
        name="WCHAR",
        description="Single Unicode character (2 bytes, UTF-16)",
        size_bits=16,
        range_str=None,
        category="string",
    ),
    "STRING": TypeDescription(
        name="STRING",
        description="Variable-length ASCII string (up to 254 characters, default 254)",
        size_bits=2048,  # default STRING[254]: 2 overhead bytes + 254 chars = 256 bytes = 2048 bits
        range_str=None,
        category="string",
    ),
    "WSTRING": TypeDescription(
        name="WSTRING",
        description="Variable-length Unicode string (up to 16382 characters, UTF-16)",
        size_bits=32768,  # default WSTRING[254]: 4 overhead bytes + 254*2 bytes
        range_str=None,
        category="string",
    ),
    # ------------------------------------------------------------------ #
    # Time / duration
    # ------------------------------------------------------------------ #
    "TIME": TypeDescription(
        name="TIME",
        description="IEC 61131-3 time duration (32-bit, resolution 1 ms)",
        size_bits=32,
        range_str="T#-24d20h31m23s648ms to T#+24d20h31m23s647ms",
        category="time",
    ),
    "LTIME": TypeDescription(
        name="LTIME",
        description="IEC 61131-3 long time duration (64-bit, resolution 1 ns)",
        size_bits=64,
        range_str="LT#-106751d23h47m16s854ms775us808ns to LT#+106751d23h47m16s854ms775us807ns",
        category="time",
    ),
    # ------------------------------------------------------------------ #
    # Date
    # ------------------------------------------------------------------ #
    "DATE": TypeDescription(
        name="DATE",
        description="IEC 61131-3 date (16-bit, resolution 1 day)",
        size_bits=16,
        range_str="D#1990-01-01 to D#2168-12-31",
        category="date",
    ),
    "LDATE": TypeDescription(
        name="LDATE",
        description="Long date (32-bit, resolution 1 day)",
        size_bits=32,
        range_str="LD#1970-01-01 to LD#2554-07-21",
        category="date",
    ),
    # ------------------------------------------------------------------ #
    # Time of day
    # ------------------------------------------------------------------ #
    "TIME_OF_DAY": TypeDescription(
        name="TIME_OF_DAY",
        description="Time of day (32-bit, resolution 1 ms)",
        size_bits=32,
        range_str="TOD#00:00:00.000 to TOD#23:59:59.999",
        category="time",
    ),
    "LTIME_OF_DAY": TypeDescription(
        name="LTIME_OF_DAY",
        description="Long time of day (64-bit, resolution 1 ns)",
        size_bits=64,
        range_str="LTOD#00:00:00.000000000 to LTOD#23:59:59.999999999",
        category="time",
    ),
    # ------------------------------------------------------------------ #
    # Date and time combined
    # ------------------------------------------------------------------ #
    "DATE_AND_TIME": TypeDescription(
        name="DATE_AND_TIME",
        description="Date and time of day (64-bit BCD encoded, resolution 1 ms)",
        size_bits=64,
        range_str="DT#1990-01-01-00:00:00.000 to DT#2089-12-31-23:59:59.999",
        category="date",
    ),
    "LDATE_AND_TIME": TypeDescription(
        name="LDATE_AND_TIME",
        description="Long date and time of day (64-bit, resolution 1 ns)",
        size_bits=64,
        range_str="LDT#1970-01-01-00:00:00.000000000 to LDT#2554-07-21-23:34:33.709551615",
        category="date",
    ),
}

# Fast case-insensitive lookup index: upper-case name -> TypeDescription
_UPPER_INDEX: dict[str, TypeDescription] = {k.upper(): v for k, v in BUILTIN_TYPE_INFO.items()}


def get_type_hover_text(type_name: str) -> str | None:
    """Return a formatted markdown hover string for a built-in S7 type.

    Lookup is case-insensitive. Returns None if *type_name* is not a
    recognised built-in type.

    Example output for 'DINT'::

        **DINT** — 32-bit signed integer
        Range: -2,147,483,648 to 2,147,483,647
        Size: 32 bits
    """
    td = _UPPER_INDEX.get(type_name.upper())
    if td is None:
        return None

    lines: list[str] = [f"**{td.name}** \u2014 {td.description}"]
    if td.range_str is not None:
        lines.append(f"Range: {td.range_str}")
    lines.append(f"Size: {td.size_bits} bits")
    return "\n".join(lines)
