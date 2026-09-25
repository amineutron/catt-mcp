"""Arret du watcher de synchronisation (regression).

Le watcher est lance par Popen : quand il meurt il reste zombie tant que le
parent ne l'a pas moissonne, et os.kill(pid, 0) REUSSIT sur un zombie.
L'ancien code le croyait donc vivant, attendait 2 s pour rien, puis envoyait
un SIGKILL a un processus deja mort.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from catt_mcp.server import CattController as Controleur  # noqa: E402


def _etat(pid: int) -> str:
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]


def test_un_zombie_n_est_pas_vivant():
    processus = subprocess.Popen([sys.executable, "-c", "pass"])   # meurt aussitot
    limite = time.time() + 5
    while time.time() < limite and _etat(processus.pid) != "Z":
        time.sleep(0.05)

    assert _etat(processus.pid) == "Z", "le processus aurait du devenir zombie"
    os.kill(processus.pid, 0)          # le PID repond encore : c'est le piege
    assert Controleur._processus_vivant(processus.pid) is False

    processus.wait()                   # moisson


def test_un_processus_actif_est_vivant():
    processus = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert Controleur._processus_vivant(processus.pid) is True
    finally:
        processus.kill()
        processus.wait()


def test_pid_inexistant():
    assert Controleur._processus_vivant(999_999_999) is False
