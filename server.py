#!/usr/bin/env python3
"""
MCP Server pour catt - Cast vers TV Philips/Chromecast.

Ce serveur expose les commandes catt via le protocole MCP pour
permettre a Lyra de caster des videos YouTube et autres contenus
vers la TV Philips via Chromecast/DLNA.

Usage:
    python server.py

Configuration:
    Les settings sont lus depuis config.yaml:
    - catt.device: Nom du device (ex: "55OLED705/12")
"""

import asyncio
import glob
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import lz4.block
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False

try:
    from mcp.server import Server, ServerRequestContext
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        CallToolRequestParams,
        CallToolResult,
        ListToolsResult,
        PaginatedRequestParams,
        TextContent,
        Tool,
        ToolAnnotations,
    )
except ImportError:
    print("Error: mcp package not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)


# Adresse d'exemple (RFC 5737) : surcharger via TV_HOST ou config.yaml (tv.host)
DEFAULT_TV_HOST = "192.0.2.10"


def load_config() -> dict:
    """Charge la configuration depuis config.yaml."""
    import shutil
    # Ordre de resolution : variables d'environnement, puis YAML (CATT_CONFIG, ./config.yaml,
    # config.yaml a cote du serveur, ou celui de Lyra si le serveur vit dans son arborescence).
    config = {
        "device": os.environ.get("CATT_DEVICE", ""),
        "tv_host": os.environ.get("TV_HOST", ""),
        "adb_path": os.environ.get("ADB_PATH", "") or shutil.which("adb") or "/tmp/platform-tools/adb",
    }
    candidates = [Path(p) for p in (os.environ.get("CATT_CONFIG", ""),) if p]
    candidates += [Path.cwd() / "config.yaml", Path(__file__).parent / "config.yaml",
                   Path(__file__).parent.parent.parent / "config.yaml"]
    config_path = next((c for c in candidates if c.exists()), None)
    if config_path is not None:
        try:
            import yaml
            with open(config_path) as f:
                cfg = yaml.safe_load(f) or {}
            catt_cfg = cfg.get("catt", {}) or {}
            tv_cfg = cfg.get("tv", {}) or {}
            config["device"] = config["device"] or catt_cfg.get("device", "")
            config["tv_host"] = config["tv_host"] or tv_cfg.get("host", "")
        except Exception as e:
            print(f"Warning: Could not load {config_path}: {e}", file=sys.stderr)
    config["device"] = config["device"] or "Chromecast"
    config["tv_host"] = config["tv_host"] or DEFAULT_TV_HOST
    return config


class CattController:
    """Controleur pour catt - Cast vers Chromecast/DLNA."""

    def __init__(self, device: str, tv_host: str = DEFAULT_TV_HOST, adb_path: str = "/tmp/platform-tools/adb"):
        self.device = device
        self.tv_host = tv_host
        self.adb_path = adb_path
        self.catt_path = shutil.which("catt") or os.path.expanduser("~/.local/bin/catt")

    def _run_catt(self, *args, timeout: int = 30) -> tuple[bool, str]:
        """Execute une commande catt."""
        if not os.path.exists(self.catt_path):
            return False, "Erreur: catt non installe"

        cmd = [self.catt_path, "-d", self.device] + list(args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            output = result.stdout.strip()
            error = result.stderr.strip()

            if result.returncode == 0:
                return True, output or error or "OK"
            else:
                return False, error or output or f"Code retour: {result.returncode}"

        except subprocess.TimeoutExpired:
            return False, "Timeout"
        except Exception as e:
            return False, str(e)

    def _extract_video_id(self, url: str) -> Optional[str]:
        """Extrait l'ID YouTube d'une URL."""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
            r'^([a-zA-Z0-9_-]{11})$'
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _youtube_via_adb(self, url: str, start_time: int = 0) -> tuple[bool, str]:
        """Lance YouTube via ADB (utilise le compte Premium connecte sur la TV).

        Args:
            url: URL YouTube ou ID de video
            start_time: Position de depart en secondes (0 = debut)
        """
        if not os.path.exists(self.adb_path):
            return False, "ADB non disponible"

        # Valider et extraire l'ID - toujours obligatoire pour eviter l'injection ADB
        video_id = self._extract_video_id(url)
        if not video_id:
            return False, f"URL YouTube invalide ou non reconnue: {url[:80]!r}"

        safe_url = f"https://www.youtube.com/watch?v={video_id}"
        if start_time > 0:
            safe_url += f"&t={int(start_time)}"

        try:
            # Connecter a la TV via ADB
            subprocess.run(
                [self.adb_path, "connect", f"{self.tv_host}:5555"],
                capture_output=True,
                timeout=10
            )

            # Lancer YouTube avec des arguments separes (pas de shell=True)
            result = subprocess.run(
                [self.adb_path, "-s", f"{self.tv_host}:5555", "shell",
                 "am", "start", "-a", "android.intent.action.VIEW",
                 "-d", safe_url, "com.google.android.youtube.tv"],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                pos_str = f" @{start_time}s" if start_time > 0 else ""
                return True, f"YouTube Premium: {video_id}{pos_str}"
            else:
                error = result.stderr or result.stdout
                return False, error[:100]

        except subprocess.TimeoutExpired:
            return False, "Timeout ADB"
        except Exception as e:
            return False, str(e)

    def cast_youtube(self, url: str, use_premium: bool = True) -> str:
        """Caste une video YouTube sur la TV.

        Args:
            url: URL YouTube ou ID de video
            use_premium: Si True, utilise ADB pour beneficier de YouTube Premium (pas de pubs)
        """
        # Essayer d'abord via ADB pour YouTube Premium (pas de pubs)
        if use_premium:
            success, output = self._youtube_via_adb(url)
            if success:
                return output

        # Fallback sur catt (avec pubs)
        video_id = self._extract_video_id(url)
        if video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"

        success, output = self._run_catt("cast", url, timeout=60)

        if success:
            title_match = re.search(r'Playing "([^"]+)"', output)
            if title_match:
                return f"Lecture (Cast): {title_match.group(1)}"
            return f"Cast demarre: {video_id or url}"
        else:
            return f"Erreur: {output}"

    _ALLOWED_SCHEMES = ("https://", "http://")
    _BLOCKED_HOSTS = ("localhost", "127.", "0.", "::1", "192.168.", "10.", "172.16.", "172.17.",
                      "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
                      "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
                      "169.254.", "metadata.", "metadata.google")

    def _validate_cast_url(self, url: str) -> Optional[str]:
        """Valide une URL de cast. Retourne un message d'erreur ou None si OK."""
        from urllib.parse import urlparse
        if not any(url.startswith(s) for s in self._ALLOWED_SCHEMES):
            return "Scheme non autorise. Utiliser http:// ou https://"
        try:
            host = urlparse(url).hostname or ""
        except Exception:
            return "URL malformee"
        if any(host.startswith(b) for b in self._BLOCKED_HOSTS):
            return f"Host bloque: {host}"
        return None

    def cast_url(self, url: str) -> str:
        """Caste une URL (video, audio, etc.) sur la TV."""
        err = self._validate_cast_url(url)
        if err:
            return f"URL refusee: {err}"
        success, output = self._run_catt("cast", url, timeout=60)

        if success:
            return f"Cast demarre: {url[:50]}..."
        else:
            return f"Erreur: {output}"

    def cast_stop(self) -> str:
        """Arrete le cast en cours."""
        success, output = self._run_catt("stop")

        if success:
            return "Cast arrete"
        else:
            return f"Erreur: {output}"

    def cast_pause(self) -> str:
        """Met en pause le cast."""
        success, output = self._run_catt("pause")

        if success:
            return "Pause"
        else:
            return f"Erreur: {output}"

    def cast_resume(self) -> str:
        """Reprend le cast."""
        success, output = self._run_catt("play")

        if success:
            return "Lecture"
        else:
            return f"Erreur: {output}"

    def cast_volume(self, level: int) -> str:
        """Regle le volume du cast (0-100)."""
        level = max(0, min(100, level))
        success, output = self._run_catt("volume", str(level))

        if success:
            return f"Volume: {level}"
        else:
            return f"Erreur: {output}"

    def cast_seek(self, seconds: int) -> str:
        """Avance ou recule dans la video (en secondes, negatif pour reculer)."""
        if seconds >= 0:
            success, output = self._run_catt("seek", str(seconds))
        else:
            success, output = self._run_catt("rewind", str(abs(seconds)))

        if success:
            direction = "Avance" if seconds >= 0 else "Recul"
            return f"{direction} de {abs(seconds)}s"
        else:
            return f"Erreur: {output}"

    def cast_status(self) -> str:
        """Retourne le statut du cast en cours."""
        success, output = self._run_catt("status")

        if success:
            return output or "Aucun cast en cours"
        else:
            # "No media" n'est pas une erreur, juste pas de cast
            if "No media" in output or "Idle" in output:
                return "Aucun cast en cours"
            return f"Erreur: {output}"

    def cast_scan(self) -> str:
        """Scanne les devices disponibles."""
        cmd = [self.catt_path, "scan"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                output = result.stdout.strip()
                if output:
                    lines = output.split("\n")
                    # Filtrer la ligne "Scanning..."
                    devices = [line for line in lines if line and "Scanning" not in line]
                    if devices:
                        return "Devices:\n" + "\n".join(devices)
                return "Aucun device trouve"
            else:
                return f"Erreur: {result.stderr.strip()}"

        except subprocess.TimeoutExpired:
            return "Timeout pendant le scan"
        except Exception as e:
            return f"Erreur: {e}"

    def cast_info(self) -> str:
        """Retourne les infos du media en cours."""
        success, output = self._run_catt("info")

        if success:
            return output or "Aucune info disponible"
        else:
            return f"Erreur: {output}"

    def _get_firefox_window_title(self) -> Optional[str]:
        """Recupere le titre de la fenetre Firefox via Hyprland."""
        try:
            result = subprocess.run(
                ["hyprctl", "clients", "-j"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return None

            clients = json.loads(result.stdout)
            for client in clients:
                if 'firefox' in client.get('class', '').lower():
                    title = client.get('title', '')
                    # Enlever le suffixe " — Mozilla Firefox"
                    if ' — Mozilla Firefox' in title:
                        title = title.replace(' — Mozilla Firefox', '')
                    elif ' - Mozilla Firefox' in title:
                        title = title.replace(' - Mozilla Firefox', '')
                    return title
            return None
        except Exception:
            return None

    def _get_firefox_active_url(self) -> tuple[Optional[str], Optional[str]]:
        """Recupere l'URL et le titre de l'onglet actif de Firefox.

        Utilise le titre de la fenetre Hyprland pour matcher avec les onglets
        dans le fichier de session Firefox (plus fiable que l'index selected).

        Retourne (url, title) ou (None, error_message).
        """
        if not HAS_LZ4:
            return None, "Module lz4 non installe (pip install lz4)"

        # Recuperer le titre de la fenetre Firefox via Hyprland
        window_title = self._get_firefox_window_title()

        # Trouver le fichier de session Firefox
        home = os.path.expanduser("~")
        patterns = [
            f"{home}/.mozilla/firefox/*.default-release/sessionstore-backups/recovery.jsonlz4",
            f"{home}/.mozilla/firefox/*.default/sessionstore-backups/recovery.jsonlz4",
        ]

        recovery_file = None
        for pattern in patterns:
            matches = glob.glob(pattern)
            if matches:
                recovery_file = matches[0]
                break

        if not recovery_file:
            return None, "Fichier de session Firefox non trouve"

        try:
            # Lire le fichier jsonlz4 (header Mozilla: "mozLz40\0" + data)
            with open(recovery_file, 'rb') as f:
                magic = f.read(8)
                if magic[:8] != b'mozLz40\0':
                    return None, "Format de fichier Firefox invalide"
                compressed = f.read()

            # Decompresser
            data = lz4.block.decompress(compressed)
            session = json.loads(data)

            # Si on a le titre de la fenetre, chercher l'onglet correspondant
            if window_title:
                for window in session.get('windows', []):
                    for tab in window.get('tabs', []):
                        entries = tab.get('entries', [])
                        if entries:
                            current_entry = entries[-1]
                            tab_title = current_entry.get('title', '')
                            url = current_entry.get('url', '')
                            # Ignorer les titres vides et les pages internes
                            if not tab_title or url.startswith('about:'):
                                continue
                            # Matcher le titre (peut avoir des prefixes comme "(17) ")
                            if window_title in tab_title or tab_title in window_title:
                                return url, tab_title

            # Fallback: utiliser l'onglet marque comme selectionne
            for window in session.get('windows', []):
                selected_tab_index = window.get('selected', 1) - 1
                tabs = window.get('tabs', [])
                if 0 <= selected_tab_index < len(tabs):
                    tab = tabs[selected_tab_index]
                    entries = tab.get('entries', [])
                    if entries:
                        current_entry = entries[-1]
                        url = current_entry.get('url', '')
                        title = current_entry.get('title', '')
                        return url, title

            return None, "Aucun onglet actif trouve"

        except Exception as e:
            return None, f"Erreur lecture session Firefox: {e}"

    def cast_browser(self) -> str:
        """Caste la video de l'onglet actif de Firefox sur la TV."""
        url, title_or_error = self._get_firefox_active_url()

        if url is None:
            return f"Erreur: {title_or_error}"

        # Verifier si c'est une URL YouTube
        if 'youtube.com' in url or 'youtu.be' in url:
            result = self.cast_youtube(url)
            return f"{result} (depuis Firefox: {title_or_error[:50]}...)" if title_or_error else result

        # Verifier si c'est une URL video/stream connue
        video_domains = ['twitch.tv', 'vimeo.com', 'dailymotion.com', 'netflix.com']
        is_video = any(domain in url for domain in video_domains)

        if is_video or url.endswith(('.mp4', '.webm', '.m3u8')):
            return self.cast_url(url)

        # Pour les autres URLs, tenter quand meme
        return self.cast_url(url)

    # =========================================================================
    # Dual Cast (PC + TV synchronise) pour LightBeat
    # =========================================================================

    def _tv_media_control(self, action: str) -> bool:
        """Controle media sur la TV via ADB keycodes.

        Actions: 'pause', 'play', 'play_pause'
        """
        if not os.path.exists(self.adb_path):
            return False

        keycodes = {
            'pause': '127',        # KEYCODE_MEDIA_PAUSE
            'play': '126',         # KEYCODE_MEDIA_PLAY
            'play_pause': '85',    # KEYCODE_MEDIA_PLAY_PAUSE
            'stop': '86',          # KEYCODE_MEDIA_STOP
        }

        keycode = keycodes.get(action)
        if not keycode:
            return False

        try:
            result = subprocess.run(
                [self.adb_path, "-s", f"{self.tv_host}:5555", "shell", "input", "keyevent", keycode],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _firefox_media_control(self, action: str) -> bool:
        """Controle media sur Firefox via playerctl.

        Actions: 'pause', 'play', 'play_pause'
        """
        playerctl = shutil.which("playerctl")
        if not playerctl:
            return False

        try:
            result = subprocess.run(
                [playerctl, "-p", "firefox", action],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _firefox_get_status(self) -> tuple[Optional[str], Optional[float]]:
        """Recupere le status et la position de Firefox.

        Retourne (status, position_seconds) ou (None, None).
        Status: 'Playing', 'Paused', 'Stopped'
        """
        playerctl = shutil.which("playerctl")
        if not playerctl:
            return None, None

        try:
            # Status
            status_result = subprocess.run(
                [playerctl, "-p", "firefox", "status"],
                capture_output=True,
                text=True,
                timeout=5
            )
            status = status_result.stdout.strip() if status_result.returncode == 0 else None

            # Position (en microsecondes)
            pos_result = subprocess.run(
                [playerctl, "-p", "firefox", "position"],
                capture_output=True,
                text=True,
                timeout=5
            )
            position = None
            if pos_result.returncode == 0:
                try:
                    # playerctl retourne la position en secondes (float)
                    position = float(pos_result.stdout.strip())
                except ValueError:
                    pass

            return status, position
        except Exception:
            return None, None

    def _firefox_seek(self, position: float) -> bool:
        """Seek Firefox a une position donnee (en secondes)."""
        playerctl = shutil.which("playerctl")
        if not playerctl:
            return False

        try:
            result = subprocess.run(
                [playerctl, "-p", "firefox", "position", str(position)],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def _firefox_open_url(self, url: str) -> bool:
        """Ouvre une URL dans Firefox."""
        try:
            subprocess.Popen(
                ["firefox", "--new-tab", url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            return True
        except Exception:
            return False

    def _get_firefox_url_playerctl(self) -> Optional[str]:
        """Recupere l'URL de Firefox via playerctl (temps reel)."""
        try:
            result = subprocess.run(
                ["playerctl", "-p", "firefox", "metadata", "xesam:url"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def _get_firefox_title_playerctl(self) -> Optional[str]:
        """Recupere le titre de Firefox via playerctl (temps reel)."""
        try:
            result = subprocess.run(
                ["playerctl", "-p", "firefox", "metadata", "xesam:title"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except Exception:
            return None

    def cast_browser_dual(self) -> str:
        """Lance la video sur PC (Firefox) ET TV simultanement avec synchronisation.

        Workflow:
        1. Recuperer l'URL via playerctl (temps reel)
        2. Lancer sur TV via ADB a la meme position
        3. Demarrer le watcher pour sync bidirectionnelle
        """
        log = []

        # 1. Recuperer l'URL et titre via playerctl (temps reel)
        url = self._get_firefox_url_playerctl()
        title = self._get_firefox_title_playerctl()

        log.append(f"Fenetre: {title[:50] if title else 'N/A'}...")

        if not url:
            return "Erreur: Aucune video en cours sur Firefox (playerctl)"

        if 'youtube.com' not in url and 'youtu.be' not in url:
            return "Erreur: Dual cast supporte uniquement YouTube pour l'instant"

        video_id = self._extract_video_id(url)
        if not video_id:
            return "Erreur: Impossible d'extraire l'ID de la video"

        # Recuperer la position actuelle de Firefox
        ff_status, ff_position = self._firefox_get_status()
        if ff_position is None:
            ff_position = 0

        log.append(f"Video: {title[:40]}...")
        log.append(f"Position Firefox: {int(ff_position)}s ({int(ff_position//60)}:{int(ff_position%60):02d})")

        # 2. Lancer sur TV via ADB a la meme position
        log.append(f"Lancement TV @{int(ff_position)}s...")
        success, tv_result = self._youtube_via_adb(url, start_time=int(ff_position))
        if not success:
            return f"Erreur TV: {tv_result}"
        log.append(f"TV: {tv_result}")

        # 3. Demarrer le watcher pour sync bidirectionnelle
        log.append("Demarrage watcher sync...")
        watcher_result = self._start_sync_watcher(video_id)
        log.append(watcher_result)

        return "Dual Cast lance!\n" + "\n".join(log)

    @staticmethod
    def _state_dir() -> Path:
        """Dossier d'etat inscriptible (XDG), jamais le dossier d'installation.

        Installe en paquet, le dossier du serveur est en lecture seule : PID et
        journal ne peuvent pas y vivre.
        """
        base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
        state = Path(base) / "catt-mcp"
        state.mkdir(parents=True, exist_ok=True)
        return state

    def _start_sync_watcher(self, video_id: str, offset: float = 3.3) -> str:
        """Demarre le watcher de synchronisation en background."""
        watcher_script = Path(__file__).parent / "sync_watcher.py"
        if not watcher_script.exists():
            return f"Erreur watcher: {watcher_script} introuvable"

        # Arreter l'ancien watcher s'il existe
        self._stop_sync_watcher()

        try:
            state = self._state_dir()
            log_file = open(state / "sync_watcher.log", "w")
            process = subprocess.Popen(
                [sys.executable, str(watcher_script), self.tv_host, self.adb_path, video_id, str(offset)],
                stdout=log_file,
                stderr=log_file,
                start_new_session=True
            )

            log_file.close()          # l'enfant garde sa copie du descripteur
            self._watcher_process = process
            (state / "sync_watcher.pid").write_text(str(process.pid))

            return f"Watcher demarre (PID: {process.pid}, offset: {offset}s)"
        except Exception as e:
            return f"Erreur watcher: {e}"

    @staticmethod
    def _processus_vivant(pid: int) -> bool:
        """Vrai si le processus tourne encore ; un zombie ne compte pas.

        os.kill(pid, 0) reussit sur un zombie (le PID existe toujours), d'ou
        une attente inutile suivie d'un SIGKILL sur un processus deja mort.
        """
        try:
            etat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        except (OSError, IndexError):
            return False
        return etat != "Z"

    def _stop_sync_watcher(self) -> str:
        """Arrete le watcher : SIGTERM d'abord, SIGKILL seulement s'il resiste."""
        pid_file = self._state_dir() / "sync_watcher.pid"
        ancien = Path(__file__).parent / ".sync_watcher.pid"   # emplacement d'avant
        if not pid_file.exists() and ancien.exists():
            pid_file = ancien

        if not pid_file.exists():
            return "Pas de watcher actif"

        try:
            pid = int(pid_file.read_text().strip())
        except ValueError:
            pid_file.unlink(missing_ok=True)
            return "Watcher deja arrete"

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pid_file.unlink(missing_ok=True)
            return "Watcher deja arrete"
        except Exception as e:
            return f"Erreur arret watcher: {e}"

        processus = getattr(self, "_watcher_process", None)
        if processus is not None and processus.pid == pid:
            # c'est nous qui l'avons lance : wait() le moissonne, sinon il
            # resterait zombie et paraitrait vivant indefiniment
            try:
                processus.wait(timeout=2)
            except subprocess.TimeoutExpired:
                processus.kill()
                processus.wait(timeout=1)
            self._watcher_process = None
        else:
            # lance par une instance precedente : on observe /proc
            for _ in range(20):          # jusqu'a 2 s pour se fermer proprement
                time.sleep(0.1)
                if not self._processus_vivant(pid):
                    break
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        pid_file.unlink(missing_ok=True)
        return f"Watcher arrete (PID: {pid})"


    def cast_dual_resync(self) -> str:
        """Resynchronise PC et TV en relancant la TV a la position Firefox."""
        log = []

        # Recuperer la position Firefox
        ff_status, ff_position = self._firefox_get_status()
        if ff_position is None:
            return "Erreur: Impossible de lire la position Firefox"

        log.append(f"Position Firefox: {int(ff_position)}s")

        # Recuperer l'URL actuelle
        url, title = self._get_firefox_active_url()
        if url is None:
            return f"Erreur: {title}"

        video_id = self._extract_video_id(url)
        if not video_id:
            return "Erreur: Pas de video YouTube active"

        # Relancer TV a la position Firefox
        log.append(f"Relance TV @{int(ff_position)}s...")
        success, result = self._youtube_via_adb(url, start_time=int(ff_position))

        if success:
            log.append("Resync OK!")
        else:
            log.append(f"Erreur: {result}")

        return "\n".join(log)

    def cast_dual_stop(self) -> str:
        """Arrete le dual cast et le watcher de synchronisation."""
        log = []

        # Arreter le watcher
        result = self._stop_sync_watcher()
        log.append(result)

        # Pause Firefox
        self._firefox_media_control('pause')
        log.append("Firefox en pause")

        # Pause TV
        self._tv_media_control('pause')
        log.append("TV en pause")

        return "\n".join(log)

    def cast_dual_offset(self, offset: float) -> str:
        """Ajuste le decalage TV par rapport a Firefox.

        Args:
            offset: Decalage en secondes
                    Positif = TV en avance -> on recule la TV
                    Negatif = TV en retard -> on avance la TV

        Exemple:
            Si la TV est 2s en avance sur l'audio casque: offset=2
            Si la TV est 2s en retard sur l'audio casque: offset=-2
        """
        log = []

        # Recuperer la position Firefox
        ff_status, ff_position = self._firefox_get_status()
        if ff_position is None:
            return "Erreur: Impossible de lire la position Firefox"

        # Calculer la nouvelle position TV
        tv_position = ff_position - offset

        log.append(f"Firefox: {int(ff_position)}s")
        log.append(f"Offset: {offset:+.1f}s")
        log.append(f"Nouvelle position TV: {int(tv_position)}s")

        # Recuperer l'URL actuelle
        url, title = self._get_firefox_active_url()
        if url is None:
            return f"Erreur: {title}"

        video_id = self._extract_video_id(url)
        if not video_id:
            return "Erreur: Pas de video YouTube active"

        # Relancer TV a la position ajustee
        success, result = self._youtube_via_adb(url, start_time=max(0, int(tv_position)))

        if success:
            log.append("TV relancee avec offset!")
        else:
            log.append(f"Erreur: {result}")

        return "\n".join(log)


# Instance globale du serveur
catt: CattController = None


# Profils d'annotations MCP (ToolAnnotations) : ils disent au client ce que fait
# un outil avant de l'appeler. Aucun outil de ce serveur n'ecrase de donnee,
# donc destructiveHint reste False ; la distinction utile est la lecture seule
# et l'idempotence (rejouable sans effet cumulatif).
_READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)
_SET = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)
_ACTION = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)


# Outils de dual cast : ils pilotent Firefox via Hyprland et playerctl.
# Sans ces binaires ils echouent a l'appel, donc on ne les annonce pas.
HYPRLAND_TOOLS = frozenset({
    "cast_browser", "cast_browser_dual", "cast_dual_resync",
    "cast_dual_stop", "cast_dual_offset",
})


def _dual_cast_available() -> bool:
    """Vrai si Hyprland et playerctl sont disponibles sur cette machine."""
    return bool(shutil.which("hyprctl") and shutil.which("playerctl"))


def list_tools(all_tools: bool = False) -> list[Tool]:
    """Liste les outils disponibles.

    all_tools=True renvoie le catalogue complet, y compris le dual cast
    indisponible ici : utilise par les tests et la table du README.
    """
    tools = [
        Tool(
            name="cast_youtube",
            annotations=_ACTION,
            description="Caste une video YouTube sur la TV (URL ou ID de video)",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL YouTube (youtube.com/watch?v=xxx, youtu.be/xxx) ou ID de video"
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="cast_url",
            annotations=_ACTION,
            description="Caste une URL quelconque (video, audio, stream) sur la TV",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL du contenu a caster"
                    }
                },
                "required": ["url"]
            }
        ),
        Tool(
            name="cast_stop",
            annotations=_SET,
            description="Arrete le cast en cours sur la TV",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="cast_pause",
            annotations=_SET,
            description="Met en pause le cast en cours",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="cast_resume",
            annotations=_SET,
            description="Reprend la lecture du cast",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="cast_volume",
            annotations=_SET,
            description="Regle le volume du cast (0-100)",
            inputSchema={
                "type": "object",
                "properties": {
                    "level": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                        "description": "Niveau de volume (0-100)"
                    }
                },
                "required": ["level"]
            }
        ),
        Tool(
            name="cast_seek",
            annotations=_SET,
            description="Avance ou recule dans la video",
            inputSchema={
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "integer",
                        "description": "Secondes (positif = avancer, negatif = reculer)"
                    }
                },
                "required": ["seconds"]
            }
        ),
        Tool(
            name="cast_status",
            annotations=_READ,
            description="Retourne le statut du cast en cours",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="cast_scan",
            annotations=_READ,
            description="Scanne les devices Chromecast/DLNA disponibles sur le reseau",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="cast_info",
            annotations=_READ,
            description="Retourne les infos detaillees du media en cours",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="cast_browser",
            annotations=_ACTION,
            description="Caste la video de l'onglet actif de Firefox sur la TV (YouTube, Twitch, etc.)",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="cast_browser_dual",
            annotations=_ACTION,
            description="Lance la video sur PC (Firefox) ET TV simultanement avec synchronisation (pour LightBeat)",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="cast_dual_resync",
            annotations=_ACTION,
            description="Resynchronise PC et TV en relancant la TV a la position Firefox",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="cast_dual_stop",
            annotations=_SET,
            description="Arrete le dual cast et le watcher de synchronisation",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="cast_dual_offset",
            annotations=_SET,
            description="Ajuste le decalage TV (positif=TV en avance, negatif=TV en retard)",
            inputSchema={
                "type": "object",
                "properties": {
                    "offset": {
                        "type": "number",
                        "description": "Decalage en secondes (ex: 2 si TV en avance, -2 si TV en retard)"
                    }
                },
                "required": ["offset"]
            }
        ),
    ]

    if all_tools or _dual_cast_available():
        return tools
    return [t for t in tools if t.name not in HYPRLAND_TOOLS]


async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Execute un outil."""
    global catt

    if catt is None:
        return [TextContent(type="text", text="Erreur: catt non configure")]

    try:
        if name == "cast_youtube":
            url = arguments.get("url", "")
            result = catt.cast_youtube(url)
        elif name == "cast_url":
            url = arguments.get("url", "")
            result = catt.cast_url(url)
        elif name == "cast_stop":
            result = catt.cast_stop()
        elif name == "cast_pause":
            result = catt.cast_pause()
        elif name == "cast_resume":
            result = catt.cast_resume()
        elif name == "cast_volume":
            level = arguments.get("level", 50)
            result = catt.cast_volume(level)
        elif name == "cast_seek":
            seconds = arguments.get("seconds", 0)
            result = catt.cast_seek(seconds)
        elif name == "cast_status":
            result = catt.cast_status()
        elif name == "cast_scan":
            result = catt.cast_scan()
        elif name == "cast_info":
            result = catt.cast_info()
        elif name == "cast_browser":
            result = catt.cast_browser()
        elif name == "cast_browser_dual":
            result = catt.cast_browser_dual()
        elif name == "cast_dual_resync":
            result = catt.cast_dual_resync()
        elif name == "cast_dual_stop":
            result = catt.cast_dual_stop()
        elif name == "cast_dual_offset":
            offset = arguments.get("offset", 0)
            result = catt.cast_dual_offset(offset)
        else:
            result = f"Outil inconnu: {name}"

        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=f"Erreur: {e}")]


async def handle_list_tools(ctx: ServerRequestContext, params: PaginatedRequestParams | None) -> ListToolsResult:
    return ListToolsResult(tools=list_tools())


async def handle_call_tool(ctx: ServerRequestContext, params: CallToolRequestParams) -> CallToolResult:
    return CallToolResult(content=await call_tool(params.name, params.arguments or {}))


app = Server("catt-mcp", on_list_tools=handle_list_tools, on_call_tool=handle_call_tool)


async def main():
    """Point d'entree principal."""
    global catt

    # Charger la configuration
    config = load_config()

    catt = CattController(
        device=config["device"],
        tv_host=config["tv_host"],
        adb_path=config["adb_path"]
    )
    print(f"catt-mcp: Device: {config['device']}, TV: {config['tv_host']}", file=sys.stderr)

    # Demarrer le serveur MCP
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())


def cli() -> None:
    """Point d'entree console (pip/uvx) : lance le serveur MCP sur stdio."""
    import asyncio as _asyncio
    _asyncio.run(main())
