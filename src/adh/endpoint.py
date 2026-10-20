"""Host ADH Daemon endpoint."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping
from urllib.parse import urlsplit

DEFAULT_PORT = 8760
DEFAULT_MCP_PATH = "/mcp"


def _path(value: str | None, default: str) -> str:
    value = value or default
    return value if value.startswith("/") else f"/{value}"


@dataclass(frozen=True, slots=True)
class HostEndpoint:
    host: str
    port: int = DEFAULT_PORT
    properties: Mapping[str, Any] = field(default_factory=dict)
    source: str = "manual"

    @classmethod
    def from_url(cls, value: str) -> HostEndpoint:
        raw = value.strip()
        if not raw:
            raise ValueError("empty endpoint")
        if "://" not in raw:
            raw = f"http://{raw}"
        parsed = urlsplit(raw)
        if parsed.scheme != "http" or not parsed.hostname:
            raise ValueError(f"only HTTP URLs are supported: {value}")
        path = parsed.path.rstrip("/")
        path = path.removesuffix("/mcp")
        mcp_path = f"{path}/mcp" if path else DEFAULT_MCP_PATH
        return cls(
            host=parsed.hostname,
            port=parsed.port or DEFAULT_PORT,
            properties={"mcp_path": mcp_path, "panel_path": f"{path}/" if path else "/"},
            source="manual",
        )

    @property
    def host_for_url(self) -> str:
        return f"[{self.host}]" if ":" in self.host and not self.host.startswith("[") else self.host

    @property
    def base_url(self) -> str:
        return f"http://{self.host_for_url}:{self.port}"

    @property
    def mcp_url(self) -> str:
        return f"{self.base_url}{_path(self.properties.get('mcp_path'), DEFAULT_MCP_PATH)}"

    @property
    def panel_url(self) -> str:
        return f"{self.base_url}{_path(self.properties.get('panel_path'), '/')}"

    @property
    def key(self) -> str:
        return self.mcp_url

    def with_properties(self, values: Mapping[str, Any]) -> HostEndpoint:
        merged = {**self.properties, **values}
        return replace(self, properties=merged)

    def as_saved_url(self) -> str:
        return self.mcp_url
