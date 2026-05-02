import json
import logging
import sys
from mebuki.infrastructure.settings import settings_store


# ---------------------------------------------------------------------------
# ミニ YAML パーサー / シリアライザ（標準ライブラリのみ）
# ---------------------------------------------------------------------------

def _yaml_scalar(s: str):
    s = s.strip()
    if s in ('true', 'True', 'yes', 'Yes'):
        return True
    if s in ('false', 'False', 'no', 'No'):
        return False
    if s in ('null', 'Null', '~', ''):
        return None
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _yaml_parse_block(lines: list, start: int, base_indent: int):
    """base_indent 以上のインデントを持つブロックを再帰的にパースする。"""
    result = None
    i = start
    while i < len(lines):
        raw = lines[i]
        stripped = raw.lstrip()
        if not stripped or stripped.startswith('#'):
            i += 1
            continue
        indent = len(raw) - len(stripped)
        if indent < base_indent:
            break
        if stripped.startswith('- '):
            if not isinstance(result, list):
                result = []
            result.append(_yaml_scalar(stripped[2:]))
            i += 1
        elif stripped == '-':
            if not isinstance(result, list):
                result = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith('#')):
                i += 1
            if i < len(lines):
                ni = len(lines[i]) - len(lines[i].lstrip())
                sub, i = _yaml_parse_block(lines, i, ni)
                result.append(sub)
            else:
                result.append(None)
        elif ':' in stripped:
            if result is None:
                result = {}
            elif isinstance(result, list):
                # リスト解析中に mapping キーが現れたら親ブロックへ戻る
                break
            colon = stripped.index(':')
            key = stripped[:colon].strip()
            rest = stripped[colon + 1:].strip()
            if rest:
                result[key] = _yaml_scalar(rest)
                i += 1
            else:
                j = i + 1
                while j < len(lines) and (not lines[j].strip() or lines[j].strip().startswith('#')):
                    j += 1
                if j < len(lines):
                    ni = len(lines[j]) - len(lines[j].lstrip())
                    next_stripped = lines[j].lstrip()
                    # ni > indent: 通常の深いブロック
                    # ni == indent かつ次行がリスト項目: YAML の同インデント block sequence
                    if ni > indent or (ni == indent and (next_stripped.startswith('- ') or next_stripped == '-')):
                        sub, i = _yaml_parse_block(lines, j, ni)
                        result[key] = sub
                    else:
                        result[key] = None
                        i = j
                else:
                    result[key] = None
                    i = j
        else:
            i += 1
    return result, i


def _yaml_load(text: str) -> dict:
    lines = text.splitlines()
    result, _ = _yaml_parse_block(lines, 0, 0)
    return result or {}


def _yaml_scalar_str(v) -> str:
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if v is None:
        return 'null'
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    needs_quote = (
        not s
        or any(c in s for c in ':#{}[]|>&*!,?@`\'"\\%')
        or s[0] in ' \t'
        or s[-1] in ' \t'
        or s in ('true', 'false', 'null', 'yes', 'no', 'on', 'off',
                 'True', 'False', 'Null', 'Yes', 'No', 'On', 'Off')
    )
    if needs_quote:
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return s


def _yaml_dump(obj, indent: int = 0) -> str:
    pad = "  " * indent
    lines = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{pad}{k}:")
                sub = _yaml_dump(v, indent + 1)
                if sub:
                    lines.append(sub)
            else:
                lines.append(f"{pad}{k}: {_yaml_scalar_str(v)}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                lines.append(f"{pad}-")
                sub = _yaml_dump(item, indent + 1)
                if sub:
                    lines.append(sub)
            else:
                lines.append(f"{pad}- {_yaml_scalar_str(item)}")
    return "\n".join(lines)

logger = logging.getLogger(__name__)


def _get_mcp_command():
    """PyInstaller実行時とPython直接実行時で異なるMCPコマンドを返す"""
    if getattr(sys, 'frozen', False):
        import shutil
        symlink = shutil.which("mebuki")
        executable = symlink if symlink else sys.executable
        return executable, ["mcp", "start"]
    return sys.executable, ["-m", "mebuki", "mcp", "start"]


def cmd_mcp(args, parser):
    """MCP連携管理コマンド"""
    if not args.mcp_subcommand:
        parser.print_help()
        return

    if args.mcp_subcommand == "start":
        print("mebuki native Python MCP server 起動中 (STDIO) ...", file=sys.stderr)
        from mebuki.app.mcp_server import serve
        import asyncio
        import os

        # ロギングを無効化または stderr に向ける（STDIOを汚さないため）
        logging.getLogger().handlers = [logging.StreamHandler(sys.stderr)]

        try:
            asyncio.run(serve())
        except KeyboardInterrupt:
            pass

    elif args.mcp_subcommand == "install-claude":
        print("\nClaude Desktop への MCP サーバー登録を試みています...", file=sys.stderr)

        from pathlib import Path

        # 設定ファイルの特定
        if sys.platform == "darwin":
            config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        else:
            print(f"OS {sys.platform} は自動インストールに対応していません。手動で設定してください。", file=sys.stderr)
            return

        if not config_path.parent.exists():
            print(f"Claude Desktop の設定ディレクトリが見つかりません: {config_path.parent}", file=sys.stderr)
        else:
            executable, cmd_args = _get_mcp_command()

            # 登録内容の作成
            mcp_config = {
                "command": executable,
                "args": cmd_args,
                "env": {
                    "MEBUKI_USER_DATA_PATH": str(settings_store.user_data_path)
                }
            }

            try:
                config_data = {}
                if config_path.exists():
                    with open(config_path, "r", encoding="utf-8") as f:
                        config_data = json.load(f)

                if "mcpServers" not in config_data:
                    config_data["mcpServers"] = {}

                config_data["mcpServers"]["mebuki"] = mcp_config

                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)

                print(f"成功: Claude Desktop に 'mebuki' MCP サーバーを登録しました。", file=sys.stderr)
                print(f"設定ファイル: {config_path}", file=sys.stderr)
                print("Claude Desktop を再起動して反映させてください。", file=sys.stderr)
            except Exception as e:
                print(f"エラー: Claude Desktop への登録中に問題が発生しました: {e}", file=sys.stderr)

    elif args.mcp_subcommand == "install-goose":
        print("\nGoose への MCP 拡張登録を試みています...", file=sys.stderr)
        import os
        from pathlib import Path

        config_path = Path.home() / ".config" / "goose" / "config.yaml"
        if not config_path.parent.exists():
            print(f"Goose の設定ディレクトリが見つかりません: {config_path.parent}", file=sys.stderr)
            return

        try:
            executable, cmd_args = _get_mcp_command()

            # Goose用の設定 (YAML形式)
            config_data = {"extensions": {}}
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = _yaml_load(f.read()) or {"extensions": {}}

            if "extensions" not in config_data:
                config_data["extensions"] = {}

            config_data["extensions"]["mebuki"] = {
                "enabled": True,
                "name": "mebuki",
                "description": "Expert investment analyst tool for Japanese stocks. Provides high-precision financial data from J-QUANTS and EDINET.",
                "type": "stdio",
                "cmd": executable,
                "args": cmd_args,
                "envs": {
                    "MEBUKI_USER_DATA_PATH": str(settings_store.user_data_path)
                },
                "timeout": 300
            }

            with open(config_path, "w", encoding="utf-8") as f:
                f.write(_yaml_dump(config_data) + "\n")

            print(f"成功: Goose に 'mebuki' 拡張を登録しました。", file=sys.stderr)
            print(f"設定ファイル: {config_path}", file=sys.stderr)
        except Exception as e:
            print(f"エラー: Goose への登録中に問題が発生しました: {e}", file=sys.stderr)

    elif args.mcp_subcommand == "install-lm-studio":
        print("\nLM Studio への MCP サーバー登録を試みています...", file=sys.stderr)
        from pathlib import Path

        config_path = Path.home() / ".lmstudio" / "mcp.json"
        if not config_path.parent.exists():
            print(f"LM Studio の設定ディレクトリが見つかりません: {config_path.parent}", file=sys.stderr)
            return

        try:
            executable, cmd_args = _get_mcp_command()

            config_data = {"mcpServers": {}}
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)

            if "mcpServers" not in config_data:
                config_data["mcpServers"] = {}

            config_data["mcpServers"]["mebuki"] = {
                "command": executable,
                "args": cmd_args,
                "env": {
                    "MEBUKI_USER_DATA_PATH": str(settings_store.user_data_path)
                }
            }

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)

            print(f"成功: LM Studio に 'mebuki' MCP サーバーを登録しました。", file=sys.stderr)
            print(f"設定ファイル: {config_path}", file=sys.stderr)
            print("LM Studio を再起動して反映させてください。", file=sys.stderr)
        except Exception as e:
            print(f"エラー: LM Studio への登録中に問題が発生しました: {e}", file=sys.stderr)
