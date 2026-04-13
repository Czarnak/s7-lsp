"""AST node definitions for S7 SCL parsed structures.

These dataclasses represent the parsed elements of SCL source code.
Each node carries source position information for LSP integration
(diagnostics, go-to-definition, hover, etc.).

Design decision: We keep AST nodes protocol-independent — they don't
import lsprotocol types. The features layer converts to LSP types
when needed. This keeps the parser testable without LSP dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

# ─── Source Position ──────────────────────────────────────────


@dataclass(frozen=True)
class Position:
    """Zero-based line and character offset in source text."""

    line: int
    character: int


@dataclass(frozen=True)
class Range:
    """Start-end span in source text."""

    start: Position
    end: Position


# ─── Enums ────────────────────────────────────────────────────


class BlockKind(Enum):
    FUNCTION_BLOCK = auto()
    FUNCTION = auto()
    ORGANIZATION_BLOCK = auto()
    DATA_BLOCK = auto()
    TYPE = auto()


class VarSectionKind(Enum):
    VAR = auto()
    VAR_INPUT = auto()
    VAR_OUTPUT = auto()
    VAR_IN_OUT = auto()
    VAR_TEMP = auto()
    VAR_GLOBAL = auto()
    VAR_EXTERNAL = auto()
    VAR_CONSTANT = auto()
    VAR_RETAIN = auto()


# ─── AST Nodes ────────────────────────────────────────────────


@dataclass
class VarDeclaration:
    """A single variable declaration within a VAR section."""

    name: str
    type_name: str
    section_kind: VarSectionKind
    range: Range
    has_default: bool = False
    attribute: str | None = None


@dataclass
class VarSection:
    """A VAR_* ... END_VAR section."""

    kind: VarSectionKind
    declarations: list[VarDeclaration] = field(default_factory=list)
    range: Range = field(default_factory=lambda: Range(Position(0, 0), Position(0, 0)))
    is_constant: bool = False
    is_retain: bool = False


@dataclass
class BlockDeclaration:
    """A top-level block (FB, FC, OB, DB, TYPE)."""

    kind: BlockKind
    name: str
    return_type: str | None = None  # Only for FUNCTION
    version: str | None = None
    var_sections: list[VarSection] = field(default_factory=list)
    range: Range = field(default_factory=lambda: Range(Position(0, 0), Position(0, 0)))
    attribute: str | None = None


@dataclass
class ParsedDocument:
    """Result of parsing a single SCL source file."""

    uri: str
    blocks: list[BlockDeclaration] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)


@dataclass
class Diagnostic:
    """A parser-reported error or warning.

    Severity levels follow LSP convention:
    1 = Error, 2 = Warning, 3 = Information, 4 = Hint
    """

    message: str
    range: Range
    severity: int = 1  # Error by default
    source: str = "s7-lsp"
