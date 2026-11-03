"""明示した対応表でログインID移行を実行する。パスワードは読み出さない。"""

import argparse
import json
from pathlib import Path

from alembic import command
from alembic.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(
        description="既存資格情報のログインID対応表を指定してmigrationを適用します。"
    )
    parser.add_argument(
        "--mapping",
        type=Path,
        required=True,
        help="キーがvendor:<運営者ID>または<法人ID>:<旧メール>、値が新ログインIDのJSON",
    )
    args = parser.parse_args()
    mapping = json.loads(args.mapping.read_text(encoding="utf-8-sig"))
    if not isinstance(mapping, dict) or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in mapping.items()
    ):
        parser.error(
            "対応表は文字列のキーとログインIDからなるJSONオブジェクトで指定してください。"
        )
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.attributes["login_id_mapping"] = mapping
    command.upgrade(config, "head")


if __name__ == "__main__":
    main()
