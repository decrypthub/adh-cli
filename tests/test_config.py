from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adh.config import clear_endpoints, load_saved_endpoints, remove_endpoint, save_endpoint
from adh.endpoint import HostEndpoint


class ConfigTests(unittest.TestCase):
    def test_save_load_remove(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "connections.json"
            first = HostEndpoint.from_url("127.0.0.1:8760")
            self.assertTrue(save_endpoint(first, path))
            self.assertFalse(save_endpoint(first, path))
            loaded = load_saved_endpoints(path)
            self.assertEqual([item.mcp_url for item in loaded], [first.mcp_url])
            self.assertTrue(remove_endpoint("http://127.0.0.1:8760/mcp", path))
            self.assertEqual(clear_endpoints(path), 0)


if __name__ == "__main__":
    unittest.main()
