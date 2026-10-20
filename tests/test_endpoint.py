from __future__ import annotations

import unittest

from adh.endpoint import HostEndpoint


class EndpointTests(unittest.TestCase):
    def test_default_port_and_mcp_path(self) -> None:
        endpoint = HostEndpoint.from_url("192.168.1.8")
        self.assertEqual(endpoint.port, 8760)
        self.assertEqual(endpoint.mcp_url, "http://192.168.1.8:8760/mcp")
        self.assertEqual(endpoint.panel_url, "http://192.168.1.8:8760/")

    def test_strips_mcp_suffix(self) -> None:
        endpoint = HostEndpoint.from_url("http://127.0.0.1:8760/mcp")
        self.assertEqual(endpoint.mcp_url, "http://127.0.0.1:8760/mcp")
        self.assertEqual(endpoint.base_url, "http://127.0.0.1:8760")

    def test_rejects_https(self) -> None:
        with self.assertRaises(ValueError):
            HostEndpoint.from_url("https://example.invalid:8760")


if __name__ == "__main__":
    unittest.main()
