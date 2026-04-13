# S7-LSP

Language Server Protocol implementation for Siemens S7 PLC languages.

Provides code intelligence (diagnostics, symbols, navigation) for SCL/Structured Text, AWL/STL, and resource files — designed for integration with **Claude Code** and compatible LSP clients.

## Supported Languages

| Extension | Language | Status |
|-----------|----------|--------|
| `.scl`, `.st` | SCL / Structured Text | Phase 1 ✅ |
| `.s7dcl`, `.udt`, `.db` | SCL Declarations | Phase 1 ✅ |
| `.s7res` | Resource Files | Stub |
| `.awl` | AWL / Statement List | Stub |

## Features

### Phase 1 (Current)
- **Syntax diagnostics** — parser errors with line/column positions
- **Document symbols** — file outline (blocks, variable sections, declarations)
- **Workspace symbols** — search across all open files

### Planned
- **Go-to-definition** — jump to variable/block declarations
- **Find references** — locate all usages of a symbol
- **Hover** — type information and documentation
- **Auto-completion** — keywords, variables, types, named parameters
- **Resource file support** — multilingual text definitions
- **AWL/STL support** — statement list parsing and diagnostics

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
│   │   ├── resource_*.py    # Resource file parser (stub)
│   │   └── awl_*.py         # AWL/STL parser (stub)
│   ├── semantic/            # Symbol table, scopes, types (stub)
│   └── features/            # LSP feature handlers
│       ├── diagnostics.py   # Error/warning reporting
│       ├── symbols.py       # Document/workspace symbols
│       ├── completion.py    # Auto-complete (stub)
│       ├── hover.py         # Type info (stub)
│       ├── definition.py    # Go-to-definition (stub)
│       └── references.py    # Find references (stub)
└── claude-code-plugin/      # Claude Code plugin config
    ├── plugin.json
    └── .lsp.json
```

## License

MIT

---

*Created with Claude AI*
