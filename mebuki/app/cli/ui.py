import logging

logger = logging.getLogger(__name__)

_PAGE_SIZE = 10  # a-j


def select_stock_from_results(results: list[dict], prompt: str, cancel_text: str = "↩  戻る") -> dict | None:
    """検索結果リストから銘柄をアルファベット入力で選択する。キャンセル時は None を返す。"""
    total = len(results)
    total_pages = max(1, (total + _PAGE_SIZE - 1) // _PAGE_SIZE)
    page = 0

    while True:
        start = page * _PAGE_SIZE
        display = results[start:start + _PAGE_SIZE]

        print(prompt)
        if total_pages > 1:
            print(f"  （{total}件中 {start + 1}–{start + len(display)}件  {page + 1}/{total_pages}ページ）")
        for i, item in enumerate(display):
            print(f"  {chr(ord('a') + i)}) {item['code']}  {item['name']}  ({item['market']})")
        nav = []
        if page > 0:
            nav.append("p) 前ページ")
        if page < total_pages - 1:
            nav.append("n) 次ページ")
        nav.append(f"q) {cancel_text}")
        print("  " + "  ".join(nav))

        raw = input("選択: ").strip().lower()
        if raw == "q":
            return None
        if raw == "n" and page < total_pages - 1:
            page += 1
            continue
        if raw == "p" and page > 0:
            page -= 1
            continue
        if len(raw) == 1 and raw.isalpha():
            idx = ord(raw) - ord("a")
            if 0 <= idx < len(display):
                return display[idx]


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
