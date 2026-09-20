"""Extraction de l'ID YouTube : la validation protege la commande catt/ADB.

Implementation volontairement dupliquee avec pylips-mcp (roadmap : decision
du 2026-09-20) : les deux serveurs restent installables separement, chacun
teste sa copie. Garder les deux tables de cas identiques.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from server import CattController  # noqa: E402


def _extract(entree):
    return CattController.__new__(CattController)._extract_video_id(entree)


@pytest.mark.parametrize("entree, attendu", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42", "dQw4w9WgXcQ"),
])
def test_ids_valides(entree, attendu):
    assert _extract(entree) == attendu


@pytest.mark.parametrize("entree", [
    "", "pas une url", "https://example.com/video",
    "trop_court", "https://www.youtube.com/watch?v=trop_court",
    "; rm -rf /", "$(reboot)", "dQw4w9WgXcQ; reboot",
])
def test_entrees_rejetees(entree):
    assert _extract(entree) is None
