import logging
from typing import Any

logger = logging.getLogger(__name__)


def select_stock_from_results(results: list[dict], prompt: str, cancel_text: str = "↩  戻る") -> dict | None:
    """検索結果リストから銘柄をインタラクティブに選択する。キャンセル時は None を返す。"""
    import questionary
    choices = [
        {"name": f"{item['code']}  {item['name']}  ({item['market']})", "value": item}
        for item in results
    ]
    choices.append({"name": cancel_text, "value": None})
    return questionary.select(prompt, choices=choices).ask()


def print_banner():
    """バナーを水平グラデーション表示 (ブランドカラー: Green -> Cyan)"""
    banner_text = r"""
  ███╗   ███╗███████╗██████╗ ██╗   ██╗██╗  ██╗██╗
  ████╗ ████║██╔════╝██╔══██╗██║   ██║██║ ██╔╝██║
  ██╔████╔██║█████╗  ██████╔╝██║   ██║█████╔╝ ██║
  ██║╚██╔╝██║██╔══╝  ██╔══██╗██║   ██║██╔═██╗ ██║
  ██║ ╚═╝ ██║███████╗██████╔╝╚██████╔╝██║  ██╗██║ 🌱
  ╚═╝     ╚═╝╚══════╝╚═════╝  ╚═════╝ ╚═╝  ╚═╝╚═╝
"""
    # ブランドカラーの定義 (RGB)
    start_color = (53, 200, 95)  # #35C85F (Green)
    end_color = (27, 190, 208)    # #1BBED0 (Cyan)

    lines = banner_text.strip("\n").split("\n")
    if not lines: return

    print("")
    for line in lines:
        length = len(line)
        colored_line = ""
        for i, char in enumerate(line):
            # 水平方向の補間率
            ratio = i / max(1, length - 1)
            r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
            g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
            b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
            # TrueColor (24-bit) ANSIエスケープコード
            colored_line += f"\033[38;2;{r};{g};{b}m{char}"
        print(colored_line + "\033[0m")

    print("\033[3;38;5;250m    Sprouting Investment Insights\033[0m\n")
