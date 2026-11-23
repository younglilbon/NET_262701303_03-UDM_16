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

    def test_detects_draw_on_full_board_without_winner(self):
        size = 15

        # Tao ban co day X/O, khong co 5 quan lien tiep
        board = [
            [
                "X" if (row + 2 * col) % 4 < 2 else "O"
                for col in range(size)
            ]
            for row in range(size)
        ]

        # 1. Kiem tra ban co da day
        self.assertTrue(GameEngine.is_board_full(board))

        # 2. Kiem tra khong co nguoi choi nao thang
        for row in range(size):
            for col in range(size):
                symbol = board[row][col]
                self.assertEqual(
                    GameEngine.winning_line(board, row, col, symbol),
                    (),
                    f"Phat hien 5 quan lien tiep tai ({row}, {col})"
                )

        # 3. Tao ket qua hoa
        result = GameEngine.result(
            None,
            {"X": "alice", "O": "bob"},
            EndReason.BOARD_FULL,
            size * size,
        )

        # 4. Kiem tra ket qua
        self.assertTrue(result.is_draw)
        self.assertEqual(result.reason, EndReason.BOARD_FULL)
        self.assertIsNone(result.winner_id)
        self.assertIsNone(result.loser_id)
        self.assertIsNone(result.winner_symbol)
        self.assertEqual(result.total_moves, 225)