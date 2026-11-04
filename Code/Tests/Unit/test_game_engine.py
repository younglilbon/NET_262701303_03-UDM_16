import unittest

from Code.Server.Game_Engine.engine import GameEngine
from Code.Server.Game_Engine.models import EndReason, Symbol


class TestGameEngine(unittest.TestCase):
    def test_detects_five_in_a_row(self):
        board = [["" for _ in range(9)] for _ in range(9)]
        for col in range(4):
            board[4][col] = "X"
        board[4][4] = "X"

        line = GameEngine.winning_line(board, 4, 4, "X")

        self.assertEqual(len(line), 5)
        result = GameEngine.result(
            "X", {"X": "alice", "O": "bob"},
            EndReason.FIVE_IN_ROW, 9, line,
        )
        self.assertEqual(result.winner_id, "alice")
        self.assertEqual(result.loser_id, "bob")
        self.assertEqual(result.winner_symbol, Symbol.X)

    def test_does_not_report_four_in_a_row_as_win(self):
        board = [["" for _ in range(9)] for _ in range(9)]
        for col in range(4):
            board[4][col] = "O"

        self.assertEqual(GameEngine.winning_line(board, 4, 3, "O"), ())

    def test_detects_full_board(self):
        self.assertTrue(GameEngine.is_board_full([["X", "O"], ["O", "X"]]))
        self.assertFalse(GameEngine.is_board_full([["X", ""], ["O", "X"]]))
