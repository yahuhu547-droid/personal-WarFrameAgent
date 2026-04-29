import json
import tempfile
import unittest
from pathlib import Path

from warframe_agent.names import display_item_name


class FullItemNameTests(unittest.TestCase):
    def test_display_name_uses_full_item_data_when_alias_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            item_data_path = Path(tmp) / "items_full.json"
            item_data_path.write_text(json.dumps([
                {"item_id": "kuva_bramma", "zh_name": "赤毒布拉玛", "en_name": "Kuva Bramma"}
            ], ensure_ascii=False), encoding="utf-8")

            name = display_item_name("kuva_bramma", item_data_path=item_data_path)

        self.assertEqual(name, "赤毒布拉玛 / Kuva Bramma / kuva_bramma")


if __name__ == "__main__":
    unittest.main()
