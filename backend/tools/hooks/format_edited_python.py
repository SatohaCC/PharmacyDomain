"""エージェントのファイル編集ツールで変更されたPythonファイルのみを自動フォーマットする。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def edited_paths(event: dict[str, object]) -> list[Path]:
    """イベントから編集されたファイルパス一覧を抽出する。"""
    tool_raw = event.get("tool_name", "")
    tool = str(tool_raw).rsplit(".", 1)[-1]
    data = event.get("tool_input", {})
    if tool not in {"apply_patch", "Edit", "Write"}:
        return []
    paths: list[str] = []
    if tool == "apply_patch":
        patch = (
            data
            if isinstance(data, str)
            else (
                data.get("command", data.get("patch", ""))
                if isinstance(data, dict)
                else ""
            )
        )
        if not isinstance(patch, str):
            return []
        for line in patch.splitlines():
            for prefix in ("*** Add File: ", "*** Update File: ", "*** Move to: "):
                if line.startswith(prefix):
                    paths.append(line.removeprefix(prefix))
    else:
        path = data.get("file_path") if isinstance(data, dict) else None
        if isinstance(path, str):
            paths.append(path)
    cwd_raw = event.get("cwd", str(ROOT))
    cwd = Path(str(cwd_raw))
    files: set[Path] = set()
    for value in paths:
        path_obj = Path(value)
        resolved = (path_obj if path_obj.is_absolute() else cwd / path_obj).resolve()
        if resolved.is_relative_to(ROOT) and resolved.is_file():
            files.add(resolved)
    return sorted(files)


def edited_files(event: dict[str, object]) -> list[Path]:
    """編集されたファイルのうちPythonファイルのみを返す。"""
    return [path for path in edited_paths(event) if path.suffix == ".py"]


def get_python_exe() -> Path:
    """プロジェクトのPython実行ファイルパスを探索する。"""
    candidates = [
        ROOT / "backend/.venv",
        ROOT / ".venv",
    ]
    for base in candidates:
        exe = base / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        if exe.exists():
            return exe
    return Path(sys.executable)


def main(event: dict[str, object] | None = None) -> int:
    """変更されたPythonファイルに対してruff formatを実行する。"""
    input_data: dict[str, object]
    if event is None:
        raw = json.load(sys.stdin)
        input_data = raw if isinstance(raw, dict) else {}
    else:
        input_data = event
    files = edited_files(input_data)
    if not files:
        return 0
    python = get_python_exe()
    ruff = [str(python), "-m", "ruff"]
    results: list[int] = []
    for file in files:
        completed = subprocess.run(
            [*ruff, "format", str(file)],
            cwd=str(ROOT),
            capture_output=True,
            check=False,
        )
        results.append(completed.returncode)
    return max(results, default=0)


if __name__ == "__main__":
    sys.exit(main())
