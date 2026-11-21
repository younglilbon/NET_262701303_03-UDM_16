"""Chạy bộ kiểm thử Giai đoạn 5 dành riêng cho TV2."""

import os
import sys
import unittest


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def main() -> int:
    sys.path.insert(0, PROJECT_ROOT)

    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName(
        "Code.Tests.Unit.test_user_lobby"
    ))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName(
        "Code.Tests.Integration.test_user_lobby_tcp"
    ))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
