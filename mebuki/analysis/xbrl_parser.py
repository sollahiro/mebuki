"""
XBRL解析モジュール

インラインXBRL（HTML形式）からセクションを抽出します。
XBRLインスタンス文書（XML形式）からテキストブロックを抽出します。
"""

import logging
import re
import html
from typing import Optional, Dict, List
from pathlib import Path

from ..constants.xbrl import XBRL_SECTIONS

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logging.warning("beautifulsoup4がインストールされていません。XBRL解析機能は使用できません。")

try:
    import xml.etree.ElementTree as ET
    ET_AVAILABLE = True
except ImportError:
    ET_AVAILABLE = False
    logging.warning("xml.etree.ElementTreeが利用できません。XBRL解析機能は使用できません。")

logger = logging.getLogger(__name__)


class XBRLParser:
    """XBRL解析クラス"""
    
    # セクション定義はconfig.pyのXBRL_SECTIONSを使用
    # 後方互換性のためにクラス属性としてもエイリアスを定義
    COMMON_SECTIONS = XBRL_SECTIONS
    
    def __init__(self):
        """初期化"""
        if not BS4_AVAILABLE:
            logger.warning("beautifulsoup4がインストールされていません。")
    
    def _find_section(self, soup: BeautifulSoup, section_title: str) -> Optional[str]:
        """
        セクションを検索してテキストを抽出

        Args:
            soup: BeautifulSoupオブジェクト
            section_title: セクションタイトル（部分一致）

        Returns:
            セクションテキスト（見つからない場合はNone）
        """
        if not BS4_AVAILABLE:
            return None
        
        # セクションタイトルを含む要素を検索
        # 有価証券報告書の構造に応じて検索パターンを調整
        
        # パターン1: 見出しタグ（h1-h6）で検索
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            if section_title in heading.get_text():
                # 次の見出しまでを取得
                content = []
                current = heading.next_sibling
                while current:
                    # 次の見出しが見つかったら終了
                    # currentがTagオブジェクトの場合のみname属性にアクセス
                    try:
                        # BeautifulSoupのTagオブジェクトの場合
                        if hasattr(current, 'name') and hasattr(current, 'get_text'):
                            if getattr(current, 'name', None) in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                                break
                            text = current.get_text(strip=True)
                            if text:
                                content.append(text)
                        elif isinstance(current, str):
                            text = current.strip()
                            if text:
                                content.append(text)
                    except (AttributeError, TypeError):
                        # 属性アクセスエラーの場合はスキップ
                        pass
                    
                    # next_siblingが存在する場合のみ取得（NavigableStringやTagオブジェクトの場合）
                    try:
                        if hasattr(current, 'next_sibling'):
                            current = current.next_sibling  # type: ignore
                        else:
                            break
                    except (AttributeError, TypeError):
                        break
                
                if content:
                    return "\n".join(content)
        
        # パターン2: divやpタグ内で検索
        elements = soup.find_all(['div', 'p', 'section'])
        for elem in elements:
            text = elem.get_text()
            if section_title in text:
                # セクションタイトルを含む要素のテキストを取得
                return elem.get_text(separator="\n", strip=True)
        
        return None
    
    def extract_section(
        self,
        xbrl_dir: Path,
        section_name: str
    ) -> Optional[str]:
        """
        XBRLディレクトリから指定セクションを抽出

        Args:
            xbrl_dir: XBRL展開ディレクトリのパス
            section_name: セクション名（例: "経営方針、経営環境及び対処すべき課題等"）

        Returns:
            セクションテキスト（見つからない場合はNone）
        """
        if not BS4_AVAILABLE:
            logger.warning("beautifulsoup4がインストールされていないため、XBRL解析をスキップします。")
            return None
        
        if not xbrl_dir.exists() or not xbrl_dir.is_dir():
            logger.warning(f"XBRLディレクトリが存在しません: {xbrl_dir}")
            return None
        
        # インラインXBRLファイルを検索（通常はPublicDocディレクトリ内）
        # 文書によっては XBRL/PublicDoc のように入れ子になっている場合があるため、
        # ディレクトリ全体から PublicDoc を再帰的に探すか、HTMLファイルを直接探す
        html_files = list(xbrl_dir.rglob("*.html")) + list(xbrl_dir.rglob("*.htm"))
        
        # 不要なHTML（監査報告書など）を除外するためのフィルタリング
        # 本文が含まれるファイル（honbun, ixbrlなど）を優先
        if html_files:
            priority_files = [f for f in html_files if "honbun" in f.name or "ixbrl" in f.name]
            if priority_files:
                html_files = priority_files
        
        if not html_files:
            logger.warning(f"HTMLファイルが見つかりませんでした: {xbrl_dir}")
            return None
        
        # 各HTMLファイルを順番に解析
        for html_file in html_files:
            try:
                with open(html_file, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # lxmlが利用可能な場合は高速なlxmlを使用、そうでない場合はhtml.parserを使用
                try:
                    soup = BeautifulSoup(content, "lxml")
                except Exception:
                    logger.debug("lxmlが利用できないため、html.parserを使用します")
                    soup = BeautifulSoup(content, "html.parser")
                
                # セクションを検索
                section_text = self._find_section(soup, section_name)
                
                if section_text:
                    # テキスト整形
                    # HTMLタグ除去、余分な空白・改行削除
                    lines = section_text.split("\n")
                    cleaned_lines = []
                    for line in lines:
                        line = line.strip()
                        if line:
                            cleaned_lines.append(line)
                    
                    result = "\n".join(cleaned_lines)
                    
                    # 長すぎる場合は切り詰め（10,000文字まで）
                    if len(result) > 10000:
                        result = result[:10000] + "..."
                    
                    logger.info(f"セクション抽出成功: {section_name} ({len(result)}文字) - File: {html_file.name}")
                    return result
            
            except Exception as e:
                logger.error(f"XBRL解析エラー: {html_file} - {e}")
                continue
        
        logger.warning(f"全HTMLファイルを探索しましたが、セクションが見つかりませんでした: {section_name}")
        return None
    
    def extract_mda(self, xbrl_dir: Path) -> Optional[str]:
        """
        経営者による財政状態、経営成績及びキャッシュ・フローの状況の分析（MD&A）を抽出

        Args:
            xbrl_dir: XBRL展開ディレクトリのパス

        Returns:
            MD&Aテキスト
        """
        sections = self.extract_sections_by_type(xbrl_dir)
        return sections.get('D')
    
    
    def _detect_report_type(self, xbrl_dir: Path) -> str:
        """
        報告書タイプを判定
        
        Args:
            xbrl_dir: XBRL展開ディレクトリのパス
            
        Returns:
            'annual' (有価証券報告書) または 'interim' (半期報告書)
        """
        # XBRLインスタンス文書を検索
        xml_files = []
        for xml_file in xbrl_dir.rglob("*.xml"):
            if any(suffix in xml_file.name for suffix in ['_lab.xml', '_pre.xml', '_cal.xml', '_def.xml']):
                continue
            xml_files.append(xml_file)
        
        xbrl_files = list(xbrl_dir.rglob("*.xbrl"))
        xml_files.extend(xbrl_files)
        
        # ファイル名から判定
        for xml_file in xml_files:
            filename = xml_file.name.lower()
            # 有価証券報告書: jpcrp040300 または jpcrp030000
            if any(code in filename for code in ['jpcrp040300', '040300', 'jpcrp030000', '030000']):
                return 'annual'
            # 半期報告書: jpcrp030300, 四半期報告書: jpcrp040400
            if any(code in filename for code in ['jpcrp030300', '030300', 'jpcrp040400', '040400', 'jpcrp040500', '040500']):
                return 'interim'
        
        # XMLファイルの内容から判定
        for xml_file in xml_files[:5]:  # 最初の5ファイルをチェック
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # DocumentType要素を検索
                for elem in root.iter():
                    tag = elem.tag
                    if '}' in tag:
                        tag = tag.split('}')[1]
                    
                    if 'DocumentType' in tag or 'documentType' in tag:
                        text = elem.text
                        if text:
                            text_lower = text.lower()
                            if '有価証券報告書' in text or 'annual' in text_lower or '040300' in text:
                                return 'annual'
                            if '半期報告書' in text or 'interim' in text_lower or 'quarterly' in text_lower or '030300' in text:
                                return 'interim'
            except Exception:
                continue
        
        # デフォルトは有価証券報告書
        logger.warning(f"報告書タイプを判定できませんでした。デフォルトで有価証券報告書として処理します: {xbrl_dir}")
        return 'annual'
    
    def extract_sections_by_type(
        self, 
        xbrl_dir: Path, 
        report_type: Optional[str] = None
    ) -> Dict[str, str]:
        """
        共通ロジックでセクションを抽出（報告書タイプに関係なく）
        
        Args:
            xbrl_dir: XBRL展開ディレクトリのパス
            report_type: 報告書タイプ（'annual' または 'interim'）。Noneの場合は自動判定
            
        Returns:
            {セクションID: テキスト} の辞書（見つからない場合は空文字列）
        """
        if not ET_AVAILABLE:
            logger.warning("xml.etree.ElementTreeが利用できないため、XBRLテキスト抽出をスキップします。")
            return {}
        
        if not xbrl_dir.exists() or not xbrl_dir.is_dir():
            logger.warning(f"XBRLディレクトリが存在しません: {xbrl_dir}")
            return {}
        
        # 報告書タイプを判定（指定されていない場合）
        if report_type is None:
            report_type = self._detect_report_type(xbrl_dir)
        
        is_interim = (report_type == 'interim')
        if is_interim:
            logger.info(f"半期報告書として処理します。一部セクションがない場合があります: {xbrl_dir}")
        
        # 共通セクション定義を使用
        sections = self.COMMON_SECTIONS
        logger.info(f"抽出対象セクション数: {len(sections)}")
        
        # XBRLインスタンス文書を検索
        xml_files = []
        for xml_file in xbrl_dir.rglob("*.xml"):
            if any(suffix in xml_file.name for suffix in ['_lab.xml', '_pre.xml', '_cal.xml', '_def.xml']):
                continue
            xml_files.append(xml_file)
        
        xbrl_files = list(xbrl_dir.rglob("*.xbrl"))
        xml_files.extend(xbrl_files)
        
        if not xml_files:
            logger.warning(f"XBRLインスタンス文書が見つかりません: {xbrl_dir}")
            return {}
        
        # 全てのテキストブロック要素を抽出（要素名ベース）
        all_text_blocks = {}
        namespaces = {}
        
        for xml_file in xml_files:
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # 名前空間を登録
                for prefix, uri in root.attrib.items():
                    if prefix.startswith('xmlns'):
                        if prefix == 'xmlns':
                            namespaces[''] = uri
                        else:
                            ns_prefix = prefix.replace('xmlns:', '')
                            namespaces[ns_prefix] = uri
                
                # 全ての要素を走査してテキストブロックを検索
                for elem in root.iter():
                    tag = elem.tag
                    # 名前空間を除去
                    if '}' in tag:
                        local_tag = tag.split('}')[1]
                    else:
                        local_tag = tag
                    
                    # TextBlockで終わる要素を検索
                    if local_tag.endswith('TextBlock') or 'TextBlock' in local_tag:
                        # 要素のテキストを取得
                        text = self._extract_text_from_html_element_simple(elem)
                        if text and len(text) > 50:
                            # 要素名をキーとして保存
                            all_text_blocks[local_tag] = text
                            
            except ET.ParseError as e:
                logger.warning(f"XMLパースエラー: {xml_file.name} - {e}")
                continue
            except Exception as e:
                logger.error(f"XBRLテキスト抽出エラー: {xml_file.name} - {e}", exc_info=True)
                continue
        
        # セクション定義に基づいて抽出
        result = {}
        for section_id, section_def in sections.items():
            section_text = None
            
            # 方法1: 要素名で検索（完全一致または部分一致）
            target_elements = section_def.get('xbrl_elements', [])
            for xbrl_element in target_elements:
                for block_name, block_text in all_text_blocks.items():
                    if xbrl_element in block_name or block_name.endswith(xbrl_element):
                        section_text = block_text
                        logger.debug(f"セクション {section_id} ({section_def['title']}) を要素名で発見: {block_name}")
                        break
                if section_text:
                    break
            
            
            # 方法4: キーワードで検索（フォールバック）
            # 完全な項目名のフレーズで検索（簡略化されたキーワードは使用しない）
            if not section_text:
                section_title = section_def.get('title', '')
                
                for block_name, block_text in all_text_blocks.items():
                    # XBRL要素名をチェック（英語の要素名）
                    xbrl_elements = section_def.get('xbrl_elements', [])
                    element_found = False
                    for element in xbrl_elements:
                        if element in block_name or block_name.endswith(element):
                            element_found = True
                            break
                    
                    # 完全な項目名のフレーズで検索（様々なパターン）
                    title_patterns = [
                        section_title,  # 完全一致
                        f'【{section_title}】',  # 【項目名】
                        f'{section_title}】',  # 項目名】
                        f'【{section_title}',  # 【項目名
                    ]
                    
                    # 完全な項目名のフレーズまたはXBRL要素名が見つかった場合
                    if element_found or any(pattern in block_text[:500] for pattern in title_patterns):
                        section_text = block_text
                        logger.debug(f"セクション {section_id} ({section_def['title']}) を完全な項目名で発見")
                        break
            
            if section_text:
                # 項目名のフレーズで始まるように調整
                section_text = self._ensure_starts_with_section_title(section_text, section_def['title'])
                result[section_id] = section_text
                logger.info(f"セクション {section_id} ({section_def['title']}) 抽出成功: {len(section_text)}文字")
            else:
                # セクションが見つからない場合
                # 半期報告書の場合は正常な動作として扱う（一部セクションがないことがある）
                if is_interim:
                    logger.debug(f"セクション {section_id} ({section_def['title']}) が見つかりませんでした（半期報告書のため正常です）")
                else:
                    logger.debug(f"セクション {section_id} ({section_def['title']}) が見つかりませんでした（空文字列を返します）")
                result[section_id] = ""
        
        return result
    
    def _ensure_starts_with_section_title(self, text: str, section_title: str) -> str:
        """
        抽出したテキストが項目名のフレーズで始まるように調整
        
        Args:
            text: 抽出されたテキスト
            section_title: セクションのタイトル（項目名）
            
        Returns:
            項目名のフレーズで始まるように調整されたテキスト
        """
        # 既に項目名で始まっている場合はそのまま返す
        if text.strip().startswith(section_title):
            return text.strip()
        
        # 項目名のフレーズを探す（様々なパターン）
        patterns = [
            f'【{section_title}】',  # 【項目名】
            f'{section_title}】',  # 項目名】
            f'【{section_title}',  # 【項目名
            section_title,  # 完全一致
        ]
        
        # テキスト内で項目名のフレーズを探す
        best_match = None
        best_idx = len(text)
        
        for pattern in patterns:
            idx = text.find(pattern)
            if idx != -1 and idx < best_idx:
                best_match = pattern
                best_idx = idx
        
        if best_match is not None:
            # 項目名のフレーズが見つかった位置から開始
            adjusted_text = text[best_idx:]
            
            # 項目名のフレーズの前にある数字や記号を除去
            # 例：「２【事業の内容】」→「事業の内容」で始まるように
            # 例：「事業の内容】」→「事業の内容」で始まるように
            if adjusted_text.startswith('【'):
                # 【項目名】の場合
                if adjusted_text.startswith(f'【{section_title}】'):
                    adjusted_text = adjusted_text[len(f'【{section_title}】'):].lstrip()
                    adjusted_text = section_title + (' ' if adjusted_text else '') + adjusted_text
                elif adjusted_text.startswith(f'【{section_title}'):
                    # 【項目名 の場合
                    end_idx = adjusted_text.find('】')
                    if end_idx != -1:
                        adjusted_text = adjusted_text[end_idx + 1:].lstrip()
                        adjusted_text = section_title + (' ' if adjusted_text else '') + adjusted_text
            elif adjusted_text.startswith(f'{section_title}】'):
                # 項目名】の場合
                adjusted_text = adjusted_text[len(f'{section_title}】'):].lstrip()
                adjusted_text = section_title + (' ' if adjusted_text else '') + adjusted_text
            elif not adjusted_text.startswith(section_title):
                # 項目名で始まっていない場合、項目名を探してその位置から開始
                title_idx = adjusted_text.find(section_title)
                if title_idx != -1:
                    # 項目名の前の部分を除去
                    adjusted_text = adjusted_text[title_idx:]
                    # 項目名の後に】がある場合は除去
                    if adjusted_text.startswith(section_title + '】'):
                        adjusted_text = adjusted_text[len(section_title + '】'):].lstrip()
                        adjusted_text = section_title + (' ' if adjusted_text else '') + adjusted_text
                    elif adjusted_text.startswith(section_title):
                        # 項目名の直後にスペースがない場合は追加
                        if len(adjusted_text) > len(section_title) and adjusted_text[len(section_title)] not in [' ', '　', '】', '】']:
                            adjusted_text = section_title + ' ' + adjusted_text[len(section_title):].lstrip()
            
            return adjusted_text.strip()
        
        # 項目名のフレーズが見つからない場合は、項目名を先頭に追加
        return section_title + ' ' + text.strip()
    
    
    def _extract_text_from_html_element_simple(self, element: ET.Element) -> str:
        """HTMLタグを含む要素からテキストを抽出（テーブル判定なし）"""
        # 要素のテキストを取得
        text_parts = []
        
        # 要素の直接のテキスト
        if element.text:
            text = element.text.strip()
            if text:
                text_parts.append(text)
        
        # 子要素からテキストを再帰的に抽出
        for child in element:
            child_text = self._extract_text_from_html_element_simple(child)
            if child_text:
                text_parts.append(child_text)
            
            # 子要素の後のテキスト（tail）
            if child.tail:
                tail_text = child.tail.strip()
                if tail_text:
                    text_parts.append(tail_text)
        
        combined_text = '\n'.join(text_parts)
        
        # HTMLエンティティをデコード
        combined_text = html.unescape(combined_text)
        
        # HTMLタグを除去（正規表現で）
        combined_text = re.sub(r'<[^>]+>', '', combined_text)
        
        # 余分な空白を整理
        combined_text = re.sub(r'\s+', ' ', combined_text)
        combined_text = combined_text.strip()
        
        return combined_text
    
    def extract_text_from_xbrl(self, xbrl_dir: Path, exclude_tables: bool = False) -> str:
        """
        XBRLディレクトリからテキストブロックを抽出（後方互換性のためのメソッド）
        
        注意: このメソッドは後方互換性のために残されています。
        新しいコードでは extract_sections_by_type を使用してください。
        
        Args:
            xbrl_dir: XBRLが展開されたディレクトリ
            exclude_tables: 表を除外するかどうか（現在は無視されます）
            
        Returns:
            抽出されたテキスト（全セクションを結合）
        """
        # 新しいメソッドを使用してセクションを抽出
        sections = self.extract_sections_by_type(xbrl_dir)
        
        # セクションを順序付きで結合（A→B→C...の順）
        section_order = sorted(sections.keys())
        combined_texts = []
        for section_id in section_order:
            text = sections[section_id]
            if text:
                combined_texts.append(text)
        
        return '\n\n'.join(combined_texts)
    

