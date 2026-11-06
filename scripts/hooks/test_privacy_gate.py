import pytest

from scripts.hooks import privacy_gate


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_scan_reports_locations_without_private_content(tmp_path, encoding):
    text = "C:" + "/Users/private-person/project"
    (tmp_path / "sample.md").write_text(text + "\nsecret-marker", encoding=encoding)
    result = privacy_gate.scan(
        tmp_path, ["sample.md", "deleted.md"], {"blocked_literals": ["secret-marker"]}
    )
    assert result == ["sample.md:1", "sample.md:2"]
    assert "private-person" not in str(result)


def test_routes_placeholders_and_binary_are_not_flagged(tmp_path):
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


def test_hook_feedback_and_stop_do_not_loop(tmp_path, monkeypatch):
    (tmp_path / "sample.md").write_text(
        "C:" + "/Users/private-person/x", encoding="utf-8"
    )
    monkeypatch.setattr(privacy_gate, "ROOT", tmp_path)
    monkeypatch.setattr(privacy_gate, "changed_paths", lambda _: ["sample.md"])
    monkeypatch.setattr(privacy_gate.Path, "home", lambda: tmp_path)
    assert (
        "additionalContext"
        in privacy_gate.main({"hook_event_name": "PostToolUse"})["hookSpecificOutput"]
    )
    assert privacy_gate.main({"hook_event_name": "Stop"})["decision"] == "block"
    assert "systemMessage" in privacy_gate.main(
        {"hook_event_name": "Stop", "stop_hook_active": True}
    )


def test_scan_detects_api_tokens_and_mynumber(tmp_path):
    text = (
        "api_key = 'ghp_123456789012345678901234567890123456'\n"
        "patient_info = {'マイナンバー': '123456789012'}\n"
        "safe_code = 'normal line'\n"
    )
    (tmp_path / "leak.py").write_text(text, encoding="utf-8")
    result = privacy_gate.scan(tmp_path, ["leak.py"], {})
    assert result == ["leak.py:1", "leak.py:2"]
