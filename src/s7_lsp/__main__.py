"""Entry point for the S7-LSP language server.

This module is invoked when running `s7-lsp` from the command line.
LSP clients can launch this binary and communicate over stdio.
"""

import argparse
import logging
import sys

from s7_lsp.server import create_server

_LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="s7-lsp",
        description="Language Server Protocol implementation for Siemens S7 PLC languages",
    )
    parser.add_argument(
        "--stdio",
        action="store_true",
        default=True,
        help="Use stdio transport (default for editor LSP clients)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="Set logging verbosity",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Write logs to file instead of stderr",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit",
    )

    args = parser.parse_args()

    if args.version:
        from s7_lsp import __version__

        print(f"s7-lsp {__version__}")
        sys.exit(0)

    # Configure logging — stderr by default, file if specified.
    # We avoid stdout because stdio transport uses it for JSON-RPC.
    log_level = _LOG_LEVELS[args.log_level]
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    if args.log_file:
        logging.basicConfig(level=log_level, format=log_format, filename=args.log_file)
    else:
        logging.basicConfig(level=log_level, format=log_format, stream=sys.stderr)

    server = create_server()
    server.start_io()


if __name__ == "__main__":
    main()
