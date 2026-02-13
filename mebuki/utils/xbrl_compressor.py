"""
XBRLテキスト圧縮モジュール

EDINETのXBRLからテキスト化した長文を、LLM投入用に一次圧縮する前処理
"""

import re
from typing import List, Set


def compress_text(text: str) -> str:
    """
    XBRLテキストを圧縮（重要セクションのみ抽出）
    
    Args:
        text: XBRLから抽出したテキスト
        
    Returns:
        圧縮後のテキスト
    """
    # 1. 監査報告書を削除
    text = _remove_audit_reports(text)
    
    # 2. 定型的な注意文を削除
    text = _remove_formal_notices(text)
    
    # 3. 重要セクションを抽出（キーワードベース）
    sections = _extract_important_sections_keyword_based(text)
    
    # 4. 抽出したセクションを結合
    compressed = '\n\n'.join(sections)
    
    # 5. 余分な空白を整理
    compressed = _cleanup_whitespace(compressed)
    
    return compressed


def _remove_audit_reports(text: str) -> str:
    """監査報告書を削除"""
    patterns = [
        r'独立監査人.*?以\s*上',
        r'監査報告書.*?以\s*上',
        r'期中レビュー報告書.*?以\s*上',
        r'監査人の結論.*?以\s*上',
        r'監査人の責任.*?以\s*上',
        r'監査法人.*?以\s*上',
        r'公認会計士.*?以\s*上',
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.DOTALL)
    
    return text


def _remove_formal_notices(text: str) -> str:
    """定型的な注意文を削除"""
    patterns = [
        r'注:.*?ご確認ください[。.]',
        r'本要約は.*?自動生成.*?',
        r'正確な情報については.*?原本.*?',
        r'有価証券報告書の原本.*?',
        r'EDINET提出書類.*?',
        r'半期報告書.*?',
        r'回次\s*第\d+期',
        r'（単位[：:：].*?）',
        r'\(単位[：:：].*?\)',
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
    
    return text


def _extract_important_sections_keyword_based(text: str) -> List[str]:
    """
    キーワードベースで重要セクションを抽出
    
    見出しパターンに頼らず、キーワードを含む行を起点として
    その周辺のテキストを抽出する
    """
    # 重要セクションのキーワード
    keywords = [
        '事業の状況', '事業内容', '事業の内容', '事業概要',
        '経営方針', '中期経営計画', '経営戦略', '経営計画', '経営環境', '経営の基本方針',
        '対処すべき課題', '課題', '経営上の課題', '優先的に対処すべき課題',
        '事業等のリスク', 'リスク', '事業リスク', 'リスク要因',
        '設備投資', '設備', '投資計画', '資本支出', '設備投資等の概要',
        'M&A', '組織再編', '合併', '買収', '統合', '再編', '企業結合',
        '株主還元', '資本政策', '配当', '配当政策', '配当方針', '株主還元方針', '配当金',
        '重要な後発事象', '後発事象', '重要な事象',
        '財政状態', '経営成績', 'キャッシュ・フロー', 'キャッシュフロー',
        '経営者による', '財政状態', '経営成績', 'キャッシュ',
    ]
    
    lines = text.split('\n')
    
    # キーワードを含む行のインデックスを取得
    keyword_line_indices = []
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        
        # 除外セクションはスキップ
        if _is_excluded_section(line_stripped):
            continue
        
        # キーワードを含む行を検出
        for keyword in keywords:
            if keyword in line_stripped:
                # 見出しらしい特徴をチェック（短い、記号付き、番号付きなど）
                if _looks_like_heading(line_stripped, keyword):
                    keyword_line_indices.append((i, keyword))
                    break
    
    if not keyword_line_indices:
        return []
    
    # 各キーワード行からセクションを抽出
    sections = []
    processed_indices: Set[int] = set()
    
    for line_idx, keyword in keyword_line_indices:
        if line_idx in processed_indices:
            continue
        
        # セクションの開始行
        start_idx = line_idx
        
        # セクションの終了行を探す（次のキーワード行または除外セクションまで）
        end_idx = len(lines)
        
        for next_line_idx, _ in keyword_line_indices:
            if next_line_idx > line_idx:
                end_idx = min(end_idx, next_line_idx)
                break
        
        # 除外セクションが来たら終了
        for i in range(line_idx + 1, min(end_idx, len(lines))):
            if _is_excluded_section(lines[i].strip()):
                end_idx = i
                break
        
        # セクションを抽出（最大1000行まで）
        section_lines = []
        for i in range(start_idx, min(end_idx, start_idx + 1000)):
            line = lines[i].strip()
            if line:
                section_lines.append(line)
            processed_indices.add(i)
        
        if section_lines:
            section_text = '\n'.join(section_lines).strip()
            # 100文字以上のセクションのみ追加
            if len(section_text) > 100:
                sections.append(section_text)
    
    return sections


def _looks_like_heading(line: str, keyword: str) -> bool:
    """
    行が見出しらしいかどうかを判定
    
    見出しの特徴:
    - 短い（200文字以内、より緩和）
    - 記号付き（【】、数字、括弧など）
    - キーワードが行の前半にある
    - または、キーワードを含む短い行
    """
    # キーワードが行に含まれているか確認
    keyword_pos = line.find(keyword)
    if keyword_pos == -1:
        return False
    
    # 長すぎる行は見出しではない（ただし、キーワードが最初の方にあれば許容）
    if len(line) > 200:
        # キーワードが最初の50文字以内にあれば、長くても見出しの可能性
        if keyword_pos > 50:
            return False
    
    # 見出しらしい記号やパターンを含む（優先度が高い）
    heading_indicators = [
        r'【', r'】',  # 角括弧
        r'^\d+', r'^[一二三四五六七八九十]+',  # 数字で始まる
        r'^[（(]\d+[）)]',  # 括弧付き数字
        r'^\d+[\.．、]',  # 数字+句点
    ]
    
    for pattern in heading_indicators:
        if re.search(pattern, line):
            return True
    
    # 記号がなくても、短くてキーワードが行の前半にあれば見出しの可能性
    if len(line) < 100 and keyword_pos < 80:
        return True
    
    # キーワードが行の最初の30文字以内にあれば、見出しの可能性が高い
    if keyword_pos < 30:
        return True
    
    return False


def _is_excluded_section(line: str) -> bool:
    """除外すべきセクションかどうか"""
    excluded_patterns = [
        r'会計方針',
        r'用語定義',
        r'監査',
        r'財務諸表',
        r'連結財務諸表',
        r'注記',
        r'附属明細書',
        r'沿革',
        r'役員',
        r'従業員',
        r'大株主',
    ]
    
    for pattern in excluded_patterns:
        if re.search(pattern, line, re.IGNORECASE):
            return True
    
    return False


def _cleanup_whitespace(text: str) -> str:
    """余分な空白を整理"""
    # 連続する改行を2つまでに
    text = re.sub(r'\n{3,}', '\n\n', text)
    # 行頭行末の空白を削除
    lines = [line.strip() for line in text.split('\n')]
    # 空行を削除（ただし段落区切りは残す）
    cleaned = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                cleaned.append('')
            prev_empty = True
        else:
            cleaned.append(line)
            prev_empty = False
    
    return '\n'.join(cleaned)


if __name__ == "__main__":
    # 使用例
    with open("xbrl_text_4689_S100QY1D.txt", "r", encoding="utf-8") as f:
        original_text = f.read()
    
    print(f"元のテキスト長: {len(original_text)} 文字")
    
    compressed = compress_text(original_text)
    
    print(f"圧縮後のテキスト長: {len(compressed)} 文字")
    print(f"圧縮率: {len(compressed) / len(original_text) * 100:.1f}%")
    print("\n" + "="*60)
    print("圧縮後のテキスト（最初の2000文字）:")
    print("="*60)
    print(compressed[:2000])
