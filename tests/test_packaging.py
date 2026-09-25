"""Paquet catt_mcp : ligne de commande et watcher lance comme module.

Avant la 0.3.0, le wheel installait des modules de premier niveau `server` et
`sync_watcher` : installes a cote de denon-mcp ou pylips-mcp (eux aussi
`server`), ils s'ecrasaient mutuellement.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from catt_mcp import server  # noqa: E402


def test_cli_help_sans_configuration(capsys):
    with pytest.raises(SystemExit) as exc:
        server.cli(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "CATT_DEVICE" in out and "TV_HOST" in out


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        server.cli(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.startswith("catt-mcp ")


def test_watcher_est_un_module_du_paquet():
    assert importlib.util.find_spec("catt_mcp.sync_watcher") is not None


def test_watcher_lance_par_module(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    captured = {}

    class FakePopen:
        pid = 4242

        def __init__(self, args, **kwargs):
            captured["args"] = args
            captured["env"] = kwargs.get("env") or {}

    monkeypatch.setattr(server.subprocess, "Popen", FakePopen)
    ctl = server.CattController("Chromecast", "192.0.2.10", "/usr/bin/adb")
    monkeypatch.setattr(ctl, "_stop_sync_watcher", lambda: "")
    assert "4242" in ctl._start_sync_watcher("dQw4w9WgXcQ")
    assert captured["args"][1:3] == ["-m", "catt_mcp.sync_watcher"]
    # la racine du depot est dans PYTHONPATH : l'enfant trouve le paquet sans installation
    assert str(ROOT) in captured["env"]["PYTHONPATH"].split(":")


def test_python_m_catt_mcp_version():
    out = subprocess.run([sys.executable, "-m", "catt_mcp", "--version"], cwd=ROOT,
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0 and out.stdout.startswith("catt-mcp ")
