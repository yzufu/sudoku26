import random
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog

from database import Database
from api import run_api

DIFFICULTY_CELLS = {"easy": 30, "medium": 40, "hard": 50}
DIFFICULTY_NAMES = {"easy": "Лёгкий", "medium": "Средний", "hard": "Сложный"}


class SudokuGenerator:
    @staticmethod
    def generate_solved():
        base = 3
        side = base * base

        def pattern(r, c):
            return (base * (r % base) + r // base + c) % side

        def shuffle(s):
            return random.sample(s, len(s))

        rBase = range(base)
        rows = [g * base + r for g in shuffle(rBase) for r in shuffle(rBase)]
        cols = [g * base + c for g in shuffle(rBase) for c in shuffle(rBase)]
        nums = shuffle(range(1, base * base + 1))

        return [[nums[pattern(r, c)] for c in cols] for r in rows]

    @staticmethod
    def remove_numbers(board, empty_cells=40):
        board_copy = [row[:] for row in board]
        cells = [(i, j) for i in range(9) for j in range(9)]
        random.shuffle(cells)
        for i, j in cells[:empty_cells]:
            board_copy[i][j] = 0
        return board_copy


class SudokuGame:
    def __init__(self, difficulty="medium"):
        self.generator = SudokuGenerator()
        self.new_game(difficulty)

    def new_game(self, difficulty="medium"):
        self.difficulty = difficulty
        empty = DIFFICULTY_CELLS[difficulty]
        self.solution = self.generator.generate_solved()
        self.board = self.generator.remove_numbers(self.solution, empty)
        self.original = [row[:] for row in self.board]
        self.mistakes = 0
        self.row = 0
        self.col = 0
        self.start_time = time.time()

    def elapsed(self):
        return int(time.time() - self.start_time)

    def load_from_dict(self, data):
        self.difficulty = data["difficulty"]
        self.board = data["board"]
        self.solution = data["solution"]
        self.original = data["original"]
        self.mistakes = data["mistakes"]
        self.row, self.col = 0, 0
        self.start_time = time.time()

    def input_number(self, num):
        if self.original[self.row][self.col] != 0:
            return False
        if num != 0 and num != self.solution[self.row][self.col]:
            self.mistakes += 1
        self.board[self.row][self.col] = num
        return True

    def check_solution(self):
        for i in range(9):
            for j in range(9):
                if self.board[i][j] == 0:
                    return "incomplete"
                if self.board[i][j] != self.solution[i][j]:
                    return "wrong"
        return "correct"

    def solve(self):
        self.board = [row[:] for row in self.solution]


PINK_BG = "#fff0f5"
BG_CELL = "#ffffff"
BG_RELATED = "#ffd9e8"
BG_SELECTED = "#ffafcc"
BG_SAME_NUM = "#fbc4db"
FG_FIXED = "#4a2545"
FG_USER = "#d6336c"
FG_WRONG = "#0024b3"
BTN_BG = "#ffc2d4"
BTN_ACTIVE = "#ff8fab"


class SudokuApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sudoku")
        self.root.resizable(False, False)
        self.root.config(bg=PINK_BG)

        self.db = Database()
        self.game = SudokuGame("medium")
        self.selected = (0, 0)
        self.cells = {}
        self._recorded = False  # чтобы не писать в БД дважды за партию

        self.build_ui()
        self.root.bind("<Key>", self.on_key)
        self.refresh_board()
        self.update_status()

    def make_button(self, parent, text, cmd, width=12):
        return tk.Button(
            parent, text=text, width=width, font=("Arial", 10),
            bg=BTN_BG, activebackground=BTN_ACTIVE, fg=FG_FIXED,
            bd=1, relief="raised", command=cmd,
        )

    def build_ui(self):
        # Верхняя панель: ошибки и сложность
        top = tk.Frame(self.root, bg=PINK_BG, padx=8, pady=6)
        top.pack(fill="x")

        self.mistakes_var = tk.StringVar()
        self.difficulty_var = tk.StringVar()

        tk.Label(top, textvariable=self.mistakes_var, font=("Arial", 11),
                 bg=PINK_BG, fg=FG_FIXED, padx=8).pack(side="left")
        tk.Label(top, textvariable=self.difficulty_var, font=("Arial", 11),
                 bg=PINK_BG, fg=FG_FIXED, padx=8).pack(side="right")

        # Игровое поле
        board_frame = tk.Frame(self.root, bd=2, relief="solid", bg=PINK_BG)
        board_frame.pack(padx=10, pady=6)
        for br in range(3):
            for bc in range(3):
                block = tk.Frame(board_frame, bd=1, relief="solid")
                block.grid(row=br, column=bc)
                for r in range(3):
                    for c in range(3):
                        row, col = br * 3 + r, bc * 3 + c
                        lbl = tk.Label(
                            block, text="", width=2, font=("Arial", 18, "bold"),
                            bg=BG_CELL, bd=1, relief="solid",
                        )
                        lbl.grid(row=r, column=c)
                        lbl.bind("<Button-1>", lambda e, rr=row, cc=col: self.select_cell(rr, cc))
                        self.cells[(row, col)] = lbl

        # Нижняя панель
        bottom = tk.Frame(self.root, bg=PINK_BG, padx=10, pady=8)
        bottom.pack(fill="x")

        digits = tk.Frame(bottom, bg=PINK_BG)
        digits.pack()
        for num in range(1, 10):
            btn = self.make_button(digits, str(num), lambda n=num: self.on_number(n), width=4)
            btn.config(font=("Arial", 12, "bold"))
            btn.pack(side="left", padx=3)

        row1 = tk.Frame(bottom, bg=PINK_BG)
        row1.pack(pady=(10, 0))
        for text, cmd in [
            ("Стереть", self.on_erase),
            ("Подсказка", self.on_hint),
            ("Решить", self.on_solve),
        ]:
            self.make_button(row1, text, cmd).pack(side="left", padx=4)

        # Выбор сложности
        row2 = tk.Frame(bottom, bg=PINK_BG)
        row2.pack(pady=(10, 0))
        for diff_key in ("easy", "medium", "hard"):
            self.make_button(
                row2, DIFFICULTY_NAMES[diff_key],
                lambda k=diff_key: self.new_game(k), width=9
            ).pack(side="left", padx=3)

        # Работа с БД
        row3 = tk.Frame(bottom, bg=PINK_BG)
        row3.pack(pady=(10, 0))
        for text, cmd in [
            ("Сохранить", self.on_save),
            ("Загрузить", self.on_load),
            ("Статистика", self.on_stats),
        ]:
            self.make_button(row3, text, cmd).pack(side="left", padx=4)

    def on_key(self, event):
        if event.char in "123456789":
            self.on_number(int(event.char))
        elif event.keysym in ("BackSpace", "Delete", "0"):
            self.on_erase()

    def select_cell(self, row, col):
        self.selected = (row, col)
        self.refresh_board()

    def refresh_board(self):
        sr, sc = self.selected
        selected_value = self.game.board[sr][sc]

        for (r, c), lbl in self.cells.items():
            value = self.game.board[r][c]
            lbl.config(text=str(value) if value else "")

            if self.game.original[r][c] != 0:
                fg = FG_FIXED
            elif value != 0 and value != self.game.solution[r][c]:
                fg = FG_WRONG
            else:
                fg = FG_USER
            lbl.config(fg=fg)

            if (r, c) == (sr, sc):
                bg = BG_SELECTED
            elif selected_value != 0 and value == selected_value:
                bg = BG_SAME_NUM
            elif r == sr or c == sc or (r // 3, c // 3) == (sr // 3, sc // 3):
                bg = BG_RELATED
            else:
                bg = BG_CELL
            lbl.config(bg=bg)

    def update_status(self):
        self.mistakes_var.set(f"Ошибки: {self.game.mistakes}")
        self.difficulty_var.set(f"Сложность: {DIFFICULTY_NAMES[self.game.difficulty]}")

    def on_number(self, num):
        r, c = self.selected
        self.game.row, self.game.col = r, c
        if not self.game.input_number(num):
            return
        self.refresh_board()
        self.update_status()
        self.check_win()

    def on_erase(self):
        self.on_number(0)

    def on_hint(self):
        r, c = self.selected
        if self.game.original[r][c] != 0:
            return
        if self.game.board[r][c] == self.game.solution[r][c] and self.game.board[r][c] != 0:
            return
        self.game.board[r][c] = self.game.solution[r][c]
        self.refresh_board()
        self.update_status()
        self.check_win()

    def on_solve(self):
        if messagebox.askyesno("Решить", "Показать решение? Текущая игра будет завершена."):
            self.game.solve()
            self.refresh_board()

    def check_win(self):
        if self.game.check_solution() == "correct":
            if not self._recorded:
                self.db.add_game(
                    self.game.difficulty,
                    self.game.mistakes,
                    self.game.elapsed(),
                    completed=True,
                )
                self._recorded = True
            messagebox.showinfo(
                "Победа!",
                f"Поздравляем, вы решили судоку!\nОшибки: {self.game.mistakes}"
            )
            self.new_game(self.game.difficulty)

    def new_game(self, difficulty):
        # фиксируем предыдущую незавершённую партию
        if not self._recorded and getattr(self.game, "board", None):
            self.db.add_game(
                self.game.difficulty,
                self.game.mistakes,
                self.game.elapsed() if hasattr(self.game, "start_time") else 0,
                completed=False,
            )
        self.game.new_game(difficulty)
        self._recorded = False
        self.selected = (0, 0)
        self.refresh_board()
        self.update_status()

    # ---------- работа с БД ----------
    def on_save(self):
        name = simpledialog.askstring("Сохранить", "Название партии:", parent=self.root)
        if not name:
            return
        self.db.save_game(name.strip(), self.game)
        messagebox.showinfo("Сохранено", f"Партия «{name}» сохранена.")

    def on_load(self):
        saves = self.db.list_saved()
        if not saves:
            messagebox.showinfo("Загрузить", "Сохранённых партий нет.")
            return

        listing = "\n".join(
            f"{s['id']}. {s['name']}  [{DIFFICULTY_NAMES[s['difficulty']]}]  {s['saved_at']}"
            for s in saves
        )
        raw = simpledialog.askstring(
            "Загрузить", f"Введите id партии:\n\n{listing}", parent=self.root
        )
        if not raw or not raw.strip().isdigit():
            return
        data = self.db.load_saved(int(raw.strip()))
        if not data:
            messagebox.showerror("Ошибка", "Партия не найдена.")
            return
        self.game.load_from_dict(data)
        self._recorded = False
        self.selected = (0, 0)
        self.refresh_board()
        self.update_status()

    def on_stats(self):
        stats = self.db.get_stats()
        if not stats:
            messagebox.showinfo("Статистика", "Пока нет сыгранных партий.")
            return
        lines = ["Сложность | Игр | Побед | Ср.ошибки | Лучшее время"]
        for s in stats:
            name = DIFFICULTY_NAMES.get(s["difficulty"], s["difficulty"])
            avg = f"{s['avg_mistakes']:.1f}" if s["avg_mistakes"] is not None else "-"
            best = f"{s['best_time']}с" if s["best_time"] else "-"
            lines.append(f"{name} | {s['total']} | {s['wins'] or 0} | {avg} | {best}")
        messagebox.showinfo("Статистика", "\n".join(lines))


if __name__ == "__main__":
    # запускаем REST API в фоне
    threading.Thread(target=run_api, daemon=True).start()

    root = tk.Tk()
    app = SudokuApp(root)
    root.mainloop()