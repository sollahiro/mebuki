import logging
from mebuki.infrastructure.settings import settings_store

logger = logging.getLogger(__name__)


class _DummyParser:
    """対話型モードで cmd_config / cmd_mcp に渡すダミーパーサー"""
    def print_help(self):
        pass


def cmd_config(args, parser):
    """設定管理コマンド"""
    if not args.config_subcommand:
        parser.print_help()
        return

    if args.config_subcommand == "show":
        settings = settings_store.get_masked()
        print("\n現在の設定 (機密情報はマスクされています):")
        print("-" * 40)
        for k, v in settings.items():
            print(f"{k:<20}: {v}")
        print("-" * 40)
        print(f"設定ファイルパス: {settings_store.config_path}")

    elif args.config_subcommand == "set":
        if not args.key or args.value is None:
            print("キーと値を指定してください。例: mebuki config set jquantsApiKey YOUR_KEY")
            return

        # マッピング（CLIからの入力をバックエンドのキー名に変換）
        key_map = {
            "jquantsApiKey": "jquantsApiKey",
            "jquants-key": "jquantsApiKey",
            "edinetApiKey": "edinetApiKey",
            "edinet-key": "edinetApiKey",
            "years": "analysisYears",
            "analysisYears": "analysisYears",
            "llm": "llmProvider",
            "llmProvider": "llmProvider"
        }

        target_key = key_map.get(args.key, args.key)
        target_value = args.value

        # LLMプロバイダーのバリデーション
        if target_key == "llmProvider":
            allowed = ["gemini", "grok", "claude", "none"]
            if target_value.lower() not in allowed:
                print(f"エラー: 無効なLLMプロバイダーです。{allowed} から選択してください。")
                return
            target_value = target_value.lower()

        settings_store.update({target_key: target_value}, save=True)
        print(f"設定を更新しました: {target_key}")

    elif args.config_subcommand == "init":
        print("\nmebuki 初期設定")
        print("-" * 40)
        j_key = input("J-QUANTS APIキー (空でスキップ): ").strip()
        e_key = input("EDINET APIキー (空でスキップ): ").strip()

        updates = {}
        if j_key: updates["jquantsApiKey"] = j_key
        if e_key: updates["edinetApiKey"] = e_key

        if updates:
            settings_store.update(updates, save=True)
            print("設定を保存しました。")
        else:
            print("変更はありません。")
