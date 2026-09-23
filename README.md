# catt-mcp

[![tests](https://github.com/amineutron/catt-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/amineutron/catt-mcp/actions/workflows/tests.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

MCP server for casting YouTube videos and media to Chromecast/DLNA devices via [catt](https://github.com/skorokithakis/catt).

Exposes 15 tools covering YouTube casting, playback control, dual-screen sync, and device discovery.

## Demo

![MCP client: the 15 tools, then cast_scan finding the TV](docs/assets/demo.gif)

Recorded on the real network with [`docs/demo/record.sh`](docs/demo/record.sh): a minimal MCP client ([`docs/demo/mcp_demo.py`](docs/demo/mcp_demo.py)) starts the server over stdio with `CATT_DEVICE` in the environment, lists the tools and calls `cast_scan` (read-only). Private IP addresses are replaced with documentation addresses.

## Tools

<!-- tools:start -->
| Outil | Rôle |
|---|---|
| `cast_youtube` | Caste une video YouTube sur la TV (URL ou ID de video) |
| `cast_url` | Caste une URL quelconque (video, audio, stream) sur la TV |
| `cast_stop` | Arrete le cast en cours sur la TV |
| `cast_pause` | Met en pause le cast en cours |
| `cast_resume` | Reprend la lecture du cast |
| `cast_volume` | Regle le volume du cast (0-100) |
| `cast_seek` | Avance ou recule dans la video |
| `cast_status` | Retourne le statut du cast en cours |
| `cast_scan` | Scanne les devices Chromecast/DLNA disponibles sur le reseau |
| `cast_info` | Retourne les infos detaillees du media en cours |
| `cast_browser` | Caste la video de l'onglet actif de Firefox sur la TV (YouTube, Twitch, etc.) |
| `cast_browser_dual` | Lance la video sur PC (Firefox) ET TV simultanement avec synchronisation (pour LightBeat) |
| `cast_dual_resync` | Resynchronise PC et TV en relancant la TV a la position Firefox |
| `cast_dual_stop` | Arrete le dual cast et le watcher de synchronisation |
| `cast_dual_offset` | Ajuste le decalage TV (positif=TV en avance, negatif=TV en retard) |
<!-- tools:end -->

### YouTube ID extraction

`_extract_video_id` (URL `watch?v=`, `youtu.be/`, `shorts/` or a bare 11-character ID, anything else rejected before it reaches `catt`/ADB) is deliberately duplicated in [pylips-mcp](https://github.com/amineutron/pylips-mcp) (`youtube_video`, TV app with Premium account). Both servers stay installable on their own; each one tests its copy with the same table of cases (`tests/test_youtube_id.py`). Decision recorded on 2026-09-20.

## Requirements

- Python 3.10+
- [catt](https://github.com/skorokithakis/catt): `pip install catt`
- [yt-dlp](https://github.com/yt-dlp/yt-dlp): `pip install yt-dlp`
- A Chromecast or DLNA-compatible device on the same network
- `lz4` (optional, for cache compression): `pip install lz4`

### Dual cast (Linux + Hyprland)

`cast_browser`, `cast_browser_dual`, `cast_dual_resync`, `cast_dual_stop` and
`cast_dual_offset` drive Firefox from the running desktop session. They are
advertised **only** when the required binaries are present:

- [Hyprland](https://hyprland.org/) with `hyprctl` in `PATH`
- `playerctl` for MPRIS playback control
- Firefox holding the video to mirror
- `lz4` (Python) to read Firefox's session cache

Without them the server starts normally and simply does not expose these five
tools, instead of failing when they are called.

## Installation en une ligne

```bash
uvx catt-mcp                 # depuis PyPI ; avant publication : uvx --from git+https://github.com/amineutron/catt-mcp catt-mcp
```

Configuration Claude Desktop / Claude Code (`mcpServers`) :

```json
{ "catt": { "command": "uvx", "args": ["catt-mcp"], "env": { "CATT_DEVICE": "Living Room TV" } } }
```

## Setup

### 1. Install dependencies

```bash
pip install mcp catt yt-dlp
```

### 2. Discover your device

```bash
catt scan
```

Note the device name (e.g. `55OLED705/12`, `Living Room TV`).

### 3. Configure

Copy `config.example.yaml` to `config.yaml`:

```yaml
catt:
  device: "55OLED705/12"   # Name from catt scan
```

### 4. Run

```bash
python server.py
```

Or with environment variable:

```bash
CATT_DEVICE="55OLED705/12" python server.py
```

The dual-screen tools (`dual_cast`, `dual_resync`, `dual_offset`) drive the TV through
ADB and need its IP address. Set it with `TV_HOST` (or `tv.host` in `config.yaml`),
for example `TV_HOST="192.0.2.10"`; the built-in default is only a placeholder.

## Claude Desktop Configuration

```json
{
  "mcpServers": {
    "catt": {
      "command": "python3",
      "args": ["/path/to/catt-mcp/server.py"],
      "env": {
        "CATT_DEVICE": "55OLED705/12"
      }
    }
  }
}
```

## License

MIT

## Part of the Lyra ecosystem

| Dépôt | Rôle |
|---|---|
| [lyra](https://github.com/amineutron/lyra) | assistant DevOps vocal, local par défaut (AGPL-3.0) |
| [fedora-agents](https://github.com/amineutron/fedora-agents) | MCP : machines virtuelles KVM et sauvegardes |
| [mcp-tracking](https://github.com/amineutron/mcp-tracking) | MCP + API + tableau de bord des tâches longues |
| [neutroncore](https://github.com/amineutron/neutroncore) | hub PWA du homelab |
| [hue-mcp](https://github.com/amineutron/hue-mcp) | MCP Philips Hue (fork de ThomasRohde/hue-mcp) |
| [pylips-mcp](https://github.com/amineutron/pylips-mcp) | MCP TV Philips |
| [denon-mcp](https://github.com/amineutron/denon-mcp) | MCP ampli Denon |
| [catt-mcp](https://github.com/amineutron/catt-mcp) | MCP Chromecast et DLNA |
