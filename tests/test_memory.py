from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout

from teaagent import MemoryCatalog
from teaagent.cli import main


class MemoryCatalogTests(unittest.TestCase):
    def test_memory_catalog_add_list_search_show(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = MemoryCatalog(tmp)

            entry = catalog.add("GraphQLite uses a SQLite extension", tags=("graph", "sqlite"))

            self.assertEqual(catalog.list()[0].memory_id, entry.memory_id)
            self.assertEqual(catalog.search("sqlite extension")[0].memory_id, entry.memory_id)
            self.assertEqual(catalog.search("graph")[0].tags, ("graph", "sqlite"))
            self.assertEqual(catalog.show(entry.memory_id).content, "GraphQLite uses a SQLite extension")

    def test_cli_memory_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            add_output = io.StringIO()
            list_output = io.StringIO()
            search_output = io.StringIO()

            with redirect_stdout(add_output):
                add_code = main(["memory", "add", "Use prompt mode for risky edits", "--tag", "policy", "--root", tmp])
            memory_id = json.loads(add_output.getvalue())["memory_id"]
            with redirect_stdout(list_output):
                list_code = main(["memory", "list", "--root", tmp])
            with redirect_stdout(search_output):
                search_code = main(["memory", "search", "risky edits", "--root", tmp])

            self.assertEqual(add_code, 0)
            self.assertEqual(list_code, 0)
            self.assertEqual(search_code, 0)
            self.assertEqual(json.loads(list_output.getvalue())[0]["memory_id"], memory_id)
            self.assertEqual(json.loads(search_output.getvalue())[0]["tags"], ["policy"])


if __name__ == "__main__":
    unittest.main()
