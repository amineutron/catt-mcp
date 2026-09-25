#!/usr/bin/env python3
"""Lanceur depuis le depot (Lyra, `python server.py`) : le code est dans catt_mcp/.

Ce fichier n'est pas dans le wheel : installe, le serveur se lance avec la
commande `catt-mcp` (ou `uvx catt-mcp`, `python -m catt_mcp`).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from catt_mcp.server import cli  # noqa: E402

if __name__ == "__main__":
    cli()
