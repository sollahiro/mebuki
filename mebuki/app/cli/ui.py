import logging
import sys
import termios
import tty

logger = logging.getLogger(__name__)


def getch() -> str:
    """1文字だけ読み取って返す（Enter不要）。TTY以外では通常のinput()にフォールバック。"""
    if not sys.stdin.isatty():
        return input().strip()[:1]
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def confirm(prompt: str) -> bool:
    """y/N プロンプトを表示し、1文字入力で即座に判定して返す。"""
    print(prompt, end="", flush=True)
    ch = getch()
    print(ch)  # 入力文字をエコー
    return ch.lower() == "y"


def print_banner():
    """バナーを水平グラデーション表示 (ブランドカラー: Green -> Cyan)"""
    banner_text = r"""
  ███╗   ███╗███████╗██████╗ ██╗   ██╗██╗  ██╗██╗
  ████╗ ████║██╔════╝██╔══██╗██║   ██║██║ ██╔╝██║
  ██╔████╔██║█████╗  ██████╔╝██║   ██║█████╔╝ ██║
  ██║╚██╔╝██║██╔══╝  ██╔══██╗██║   ██║██╔═██╗ ██║
  ██║ ╚═╝ ██║███████╗██████╔╝╚██████╔╝██║  ██╗██║
  ╚═╝     ╚═╝╚══════╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝
"""
    start_color = (53, 200, 95)   # #35C85F (Green)
    end_color = (27, 190, 208)    # #1BBED0 (Cyan)

    lines = banner_text.strip("\n").split("\n")
    if not lines:
        return

    print("", file=sys.stderr)
    for line in lines:
        length = len(line)
        colored_line = ""
        for i, char in enumerate(line):
            ratio = i / max(1, length - 1)
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            colored_line += f"\033[38;2;{r};{g};{b}m{char}"
        print(colored_line + "\033[0m", file=sys.stderr)



