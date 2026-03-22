import json
import logging
import sys
import yaml
from mebuki.infrastructure.settings import settings_store

logger = logging.getLogger(__name__)


def _get_mcp_command():
    """PyInstaller実行時とPython直接実行時で異なるMCPコマンドを返す"""
    if getattr(sys, 'frozen', False):
        import shutil
        symlink = shutil.which("mebuki")
        executable = symlink if symlink else sys.executable
        return executable, ["mcp", "start"]
    return sys.executable, ["-m", "mebuki.cli", "mcp", "start"]


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
        print("\nClaude Desktop への MCP サーバー登録を試みています...")

        import os
        from pathlib import Path

        # 設定ファイルの特定
        if sys.platform == "darwin":
            config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        elif sys.platform == "win32":
            config_path = Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
        else:
            print(f"OS {sys.platform} は自動インストールに対応していません。手動で設定してください。")
            return

        if not config_path.parent.exists():
            print(f"Claude Desktop の設定ディレクトリが見つかりません: {config_path.parent}")
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

                print(f"成功: Claude Desktop に 'mebuki' MCP サーバーを登録しました。")
                print(f"設定ファイル: {config_path}")
                print("Claude Desktop を再起動して反映させてください。")
            except Exception as e:
                print(f"エラー: Claude Desktop への登録中に問題が発生しました: {e}")

    elif args.mcp_subcommand == "install-goose":
        print("\nGoose への MCP 拡張登録を試みています...")
        import os
        from pathlib import Path

        config_path = Path.home() / ".config" / "goose" / "config.yaml"
        if not config_path.parent.exists():
            print(f"Goose の設定ディレクトリが見つかりません: {config_path.parent}")
            return

        try:
            executable, cmd_args = _get_mcp_command()

            # Goose用の設定 (YAML形式)
            config_data = {"extensions": {}}
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config_data = yaml.safe_load(f) or {"extensions": {}}

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
                yaml.dump(config_data, f, sort_keys=False)

            print(f"成功: Goose に 'mebuki' 拡張を登録しました。")
            print(f"設定ファイル: {config_path}")
        except Exception as e:
            print(f"エラー: Goose への登録中に問題が発生しました: {e}")

    elif args.mcp_subcommand == "install-lm-studio":
        print("\nLM Studio への MCP サーバー登録を試みています...")
        from pathlib import Path

        config_path = Path.home() / ".lmstudio" / "mcp.json"
        if not config_path.parent.exists():
            print(f"LM Studio の設定ディレクトリが見つかりません: {config_path.parent}")
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

            print(f"成功: LM Studio に 'mebuki' MCP サーバーを登録しました。")
            print(f"設定ファイル: {config_path}")
            print("LM Studio を再起動して反映させてください。")
        except Exception as e:
            print(f"エラー: LM Studio への登録中に問題が発生しました: {e}")
