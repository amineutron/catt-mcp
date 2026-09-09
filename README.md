# catt-mcp

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

MCP server for casting YouTube videos and media to Chromecast/DLNA devices via [catt](https://github.com/skorokithakis/catt).

Exposes 15 tools covering YouTube casting, playback control, dual-screen sync, and device discovery.

## Tools

| Tool | Description |
|------|-------------|
| `cast_youtube` | Cast a YouTube URL or video ID to the TV |
| `cast_url` | Cast any media URL (video, audio, stream) |
| `cast_stop` | Stop the current cast |
| `cast_pause` | Pause playback |
| `cast_resume` | Resume playback |
| `cast_volume` | Set cast volume (0-100) |
| `cast_seek` | Seek forward/backward (seconds) |
| `cast_status` | Get current cast status |
| `cast_scan` | Scan for available Chromecast/DLNA devices |
| `cast_info` | Get detailed info about current media |
| `cast_browser` | Cast the active Firefox tab to TV |
| `dual_cast` | Cast to both PC (Firefox) and TV simultaneously |
| `dual_resync` | Resync PC and TV playback |
| `dual_stop` | Stop dual cast and sync watcher |
| `dual_offset` | Adjust TV sync offset |

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
