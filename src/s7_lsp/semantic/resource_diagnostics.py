"""Resource diagnostics for .s7res files.

Performs checks specific to resource files:
1. Duplicate ID detection
2. Missing language codes across blocks
3. Empty entries (blocks with no translation strings)
"""

from __future__ import annotations

from s7_lsp.ast_nodes import (
    Diagnostic,
    ParsedDocument,
    VarSectionKind,
)


def _get_language_entries(block):
    """Return all VAR section STRING declarations (language entries) from a block."""
    entries = []
    for section in block.var_sections:
        if section.kind == VarSectionKind.VAR:
            for decl in section.declarations:
                if decl.type_name == "STRING":
                    entries.append(decl)
    return entries


def get_resource_diagnostics(doc: ParsedDocument) -> list[Diagnostic]:
    """Return diagnostics for a parsed .s7res resource document."""
    diagnostics: list[Diagnostic] = []

    if not doc.blocks:
        return diagnostics

    # --- Check 1: Duplicate ID detection (severity=1, Error) ---
    seen: dict[str, tuple[str, int]] = {}  # lower(name) -> (original_name, 1-based line)
    for block in doc.blocks:
        key = block.name.lower()
        first_line = block.range.start.line + 1  # convert to 1-based
        if key in seen:
            _, original_line = seen[key]
            diagnostics.append(
                Diagnostic(
                    message=f"Duplicate resource ID '{block.name}' (first defined on line {original_line})",
                    range=block.range,
                    severity=1,
                )
            )
        else:
            seen[key] = (block.name, first_line)

    # --- Collect global language codes across all blocks ---
    all_lang_codes: set[str] = set()
    for block in doc.blocks:
        for entry in _get_language_entries(block):
            all_lang_codes.add(entry.name)

    # --- Check 2: Missing language codes (severity=2, Warning) ---
    # Skip if only 0 or 1 block, or if no block has any language entries
    if len(doc.blocks) > 1 and all_lang_codes:
        for block in doc.blocks:
            block_lang_codes = {entry.name for entry in _get_language_entries(block)}
            for lang_code in sorted(all_lang_codes):
                if lang_code not in block_lang_codes:
                    diagnostics.append(
                        Diagnostic(
                            message=f"Resource '{block.name}' is missing language '{lang_code}'",
                            range=block.range,
                            severity=2,
                        )
                    )

    # --- Check 3: Empty entries (severity=3, Information) ---
    # Only flag missing translations if at least one block in the file has language entries.
    # If the entire file uses only properties, don't flag anything.
    if all_lang_codes:
        for block in doc.blocks:
            if not _get_language_entries(block):
                diagnostics.append(
                    Diagnostic(
                        message=f"Resource '{block.name}' has no translations",
                        range=block.range,
                        severity=3,
                    )
                )

    return diagnostics
