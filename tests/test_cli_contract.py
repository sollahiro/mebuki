from mebuki.app.cli import build_parser


def test_cli_contract_subcommands_exist():
    parser = build_parser()
    subparsers_action = next(
        action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
    )
    commands = set(subparsers_action.choices.keys())
    assert {"search", "analyze", "config", "mcp"}.issubset(commands)
