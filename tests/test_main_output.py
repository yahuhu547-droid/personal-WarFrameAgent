import io
import unittest
from contextlib import redirect_stdout

import main


class MainOutputTests(unittest.TestCase):
    def test_print_menu_shows_chinese_labels_and_model(self):
        buffer = io.StringIO()

        with redirect_stdout(buffer):
            main.print_menu()

        output = buffer.getvalue()

        self.assertIn("Warframe 本地交易 Agent", output)
        self.assertIn("当前对话模型：", output)
        self.assertIn("1. 查询单个物品", output)
        self.assertIn("4. 对话式交易助手", output)
        self.assertIn("q. 退出", output)


if __name__ == "__main__":
    unittest.main()
