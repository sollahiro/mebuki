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
