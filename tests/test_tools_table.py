"""Le tableau des outils du README doit correspondre exactement a list_tools()."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from catt_mcp import server  # noqa: E402


def test_readme_tools_match_server():
    names = sorted(t.name for t in server.list_tools(all_tools=True))
    doc = (ROOT / "README.md").read_text(encoding="utf-8")
    block = doc[doc.index("<!-- tools:start -->"):doc.index("<!-- tools:end -->")]
    in_readme = sorted(re.findall(r"^\| `([a-z_]+)` \|", block, re.M))
    assert in_readme == names


def test_tool_names_are_snake_case_and_unique():
    tools = server.list_tools(all_tools=True)
    names = [t.name for t in tools]
    assert len(set(names)) == len(names)
    assert all(re.fullmatch(r"[a-z][a-z0-9_]*", n) for n in names)


def test_dual_cast_tools_hidden_without_hyprland(monkeypatch):
    """Sans hyprctl ni playerctl, les outils de dual cast ne sont pas annonces."""
    monkeypatch.setattr(server.shutil, "which", lambda _: None)
    noms = {t.name for t in server.list_tools()}
    assert not (noms & server.HYPRLAND_TOOLS)
    assert "cast_youtube" in noms          # le reste du serveur repond toujours


def test_dual_cast_tools_present_with_hyprland(monkeypatch):
    """Avec les deux binaires, le catalogue est complet."""
    monkeypatch.setattr(server.shutil, "which", lambda _: "/usr/bin/x")
    noms = {t.name for t in server.list_tools()}
    assert server.HYPRLAND_TOOLS <= noms
