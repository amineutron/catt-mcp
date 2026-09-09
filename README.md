# catt-mcp

[![tests](https://github.com/amineutron/catt-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/amineutron/catt-mcp/actions/workflows/tests.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

MCP server for casting YouTube videos and media to Chromecast/DLNA devices via [catt](https://github.com/skorokithakis/catt).

Exposes 15 tools covering YouTube casting, playback control, dual-screen sync, and device discovery.

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

## Requirements

- Python 3.10+
- [catt](https://github.com/skorokithakis/catt): `pip install catt`
- [yt-dlp](https://github.com/yt-dlp/yt-dlp): `pip install yt-dlp`
- A Chromecast or DLNA-compatible device on the same network
- `lz4` (optional, for cache compression): `pip install lz4`

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
