"""catt-mcp : serveur MCP de cast Chromecast / DLNA (catt)."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("catt-mcp")
except PackageNotFoundError:  # lance depuis le depot sans installation
    __version__ = "dev"
