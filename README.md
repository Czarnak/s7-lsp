# S7-LSP

Language Server Protocol implementation for Siemens S7 PLC languages.

Provides code intelligence for SCL/Structured Text and Siemens resource files, designed for integration with **Claude Code** and compatible LSP clients.

Phases 1 through 4 from the product roadmap are complete: syntax support, semantic analysis, completion, and `.s7res` resource-file support are implemented. AWL/STL remains deferred.

## Supported Languages

| Extension | Language | Status |
| ----------- | ---------- | -------- |
| `.scl`, `.st` | SCL / Structured Text | Phases 1-3 ✅ |
| `.s7dcl`, `.udt`, `.db` | SCL Declarations | Phases 1-3 ✅ |
| `.s7res` | Resource Files | Phase 4 ✅ |
| `.awl` | AWL / Statement List | Deferred |

## Features

### Implemented

- **Syntax diagnostics** — parser errors with line/column positions
- **Semantic diagnostics** — undeclared variables, unknown type/block references, duplicate declarations, invalid assignments, and related semantic checks
- **Document symbols** — hierarchical outline of blocks, VAR sections, and declarations
- **Workspace symbols** — search across all open files, including resource entries
- **Go-to-definition** — jump to variable, block, DB field, and type declarations across open documents
- **Find references** — locate symbol usages, with optional inclusion of declarations
- **Hover** — variable, block, and built-in type information at the cursor
- **Auto-completion** — keywords, variables, built-in types, UDTs, named parameters, block names, and member access
- **Resource file support** — `.s7res` parsing, diagnostics, and symbol indexing for `MLC_` entries

### Roadmap

- **Grammar hardening and optimization** — broader real-world corpus testing, parser performance work, and incremental document sync
- **AWL/STL support** — deferred and not part of the active roadmap

## Installation

```bash
pip install s7-lsp
```

Or install from source:

```bash
git clone https://github.com/Czarnak/s7-lsp.git
cd s7-lsp
pip install -e .
```

Verify installation:

```bash
s7-lsp --version
```

## Claude Code Integration

### Option 1: Local Plugin

1. Install `s7-lsp` so the binary is in your `$PATH`
2. Copy the `claude-code-plugin/` directory into your project or a shared location
3. Register the plugin with Claude Code:

```bash
claude plugin install ./claude-code-plugin
```

### Option 2: Project-Level Configuration

Add to your project's `.claude/settings.json`:

```json
{
  "enabledPlugins": ["s7-lsp"]
}
```

### Option 3: Direct .lsp.json

Place `.lsp.json` in your project root with the server configuration (see `claude-code-plugin/.lsp.json` for the format).

### Verify LSP is Active

```bash
export ENABLE_LSP_TOOL=1
claude
```

When editing `.scl` files, Claude Code will automatically receive diagnostics and can navigate your PLC code structure.

## Development

```bash
# Clone and install in development mode
git clone https://github.com/Czarnak/s7-lsp.git
cd s7-lsp
pip install -e .

# Lint
pip install ruff
ruff check src/
ruff format src/

# Type check
pip install mypy
mypy src/s7_lsp/ --ignore-missing-imports
```

## Architecture

```
s7-lsp/
├── src/s7_lsp/
│   ├── __main__.py          # CLI entry point (stdio)
│   ├── server.py            # pygls LSP server setup
│   ├── workspace.py         # Document state management
│   ├── ast_nodes.py         # AST dataclasses
│   ├── parsers/
│   │   ├── scl_grammar.lark # SCL grammar (lark EBNF)
│   │   ├── scl_parser.py    # SCL parser + fallback scanner
│   │   ├── resource_*.py    # Resource file grammar and parser
│   │   └── awl_*.py         # AWL/STL parser stubs (deferred)
│   ├── semantic/            # Symbol table, scopes, semantic checks, type info
│   └── features/            # LSP feature handlers
│       ├── diagnostics.py   # Error/warning reporting
│       ├── symbols.py       # Document/workspace symbols
│       ├── completion.py    # Context-aware completion
│       ├── hover.py         # Hover information
│       ├── definition.py    # Go-to-definition
│       └── references.py    # Find references
└── claude-code-plugin/      # Claude Code plugin config
    ├── plugin.json
    └── .lsp.json
```

## License

MIT

---

*Created with Claude AI*
