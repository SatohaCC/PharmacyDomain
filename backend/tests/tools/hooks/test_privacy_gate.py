"""プライバシーゲートの単体テスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.hooks import privacy_gate


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_プライバシーゲート_個人パスまたは禁止文字列検出時_秘密内容を含めずファイル位置のみを報告する(
    tmp_path: Path, encoding: str
) -> None:
    text = "C:" + "/Users/private-person/project"
    (tmp_path / "sample.md").write_text(text + "\nsecret-marker", encoding=encoding)
    result = privacy_gate.scan(
        tmp_path, ["sample.md", "deleted.md"], {"blocked_literals": ["secret-marker"]}
    )
    assert result == ["sample.md:1", "sample.md:2"]
    assert "private-person" not in str(result)


def test_プライバシーゲート_プレースホルダやバイナリファイルの場合_指摘対象としない(
    tmp_path: Path,
) -> None:
    text = "\n".join(
        [
            "/users/me",
            "/home/alice",
            "D:" + "/Users/alice",
            "C:" + "/Users/$USER/x",
            "C:" + "/Users/username/x",
        ]
    )
    (tmp_path / "sample.txt").write_text(text, encoding="utf-8")
    (tmp_path / "image.bin").write_bytes(b"\0" + text.encode())
    assert privacy_gate.scan(tmp_path, ["sample.txt", "image.bin"], {}) == []


def test_プライバシーゲート_PostToolUseおよびStopイベント時_停止通知を発行しループしない(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sample.md").write_text(
        "C:" + "/Users/private-person/x", encoding="utf-8"
    )
    monkeypatch.setattr(privacy_gate, "ROOT", tmp_path)
    monkeypatch.setattr(privacy_gate, "changed_paths", lambda _: ["sample.md"])
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    out = privacy_gate.main({"hook_event_name": "PostToolUse"})
    hook_out = out.get("hookSpecificOutput")
    assert isinstance(hook_out, dict)
    assert "additionalContext" in hook_out
    assert privacy_gate.main({"hook_event_name": "Stop"})["decision"] == "block"
    assert "systemMessage" in privacy_gate.main(
        {"hook_event_name": "Stop", "stop_hook_active": True}
    )


def test_プライバシーゲート_APIトークンまたは個人番号形式の場合_正確に行番号を報告する(
    tmp_path: Path,
) -> None:
    text = (
        "api_key = 'ghp_123456789012345678901234567890123456'\n"
        "patient_info = {'マイナンバー': '123456789012'}\n"
        "safe_code = 'normal line'\n"
    )
    (tmp_path / "leak.py").write_text(text, encoding="utf-8")
    result = privacy_gate.scan(tmp_path, ["leak.py"], {})
    assert result == ["leak.py:1", "leak.py:2"]
