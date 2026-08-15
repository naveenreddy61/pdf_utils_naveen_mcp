"""Unit tests for the multi-page notebook capture session collector."""

from pathlib import Path
import os
import sys
import time
from unittest.mock import AsyncMock, patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from starlette.testclient import TestClient

from fasthtml.common import to_xml
from web_app.app import create_app
from web_app.core import tasks
from web_app.routes.capture import collect_notebook_pages, parse_task_ids
from web_app.ui.components import notebook_session_result


def _client():
    return TestClient(create_app())


def _login(client: TestClient) -> None:
    password = os.getenv("LOGIN_PASSWORD")
    if not password:
        return
    client.post("/auth", data={"password": password}, follow_redirects=False)


def _ok_result(text: str, seconds: float = 1.0) -> dict:
    return {
        "full_text": text,
        "processing_time": seconds,
        "total_input_tokens": 10,
        "total_output_tokens": 5,
    }


def test_parse_task_ids_keeps_only_hex12():
    raw = "abc,deadbeefdead, not-an-id, cafe01234567, deadbeefdead,"
    assert parse_task_ids(raw) == ["deadbeefdead", "cafe01234567", "deadbeefdead"]


def test_parse_task_ids_empty():
    assert parse_task_ids("") == []
    assert parse_task_ids(",,,") == []


def test_pending_session():
    tid = tasks.new_task("Transcribing…", 10)
    try:
        out = collect_notebook_pages([tid])
        assert out["status"] == "pending"
        assert out["done"] == 0
        assert out["total"] == 1
        assert "pages" not in out
    finally:
        tasks.pop_task(tid)


def test_done_session():
    tid = tasks.new_task()
    tasks.set_result(tid, _ok_result("hello notes"))
    try:
        out = collect_notebook_pages([tid])
        assert out["status"] == "done"
        assert out["done"] == 1
        assert out["pages"][0]["ok"] is True
        assert out["pages"][0]["full_text"] == "hello notes"
        assert out["pages"][0]["n"] == 1
    finally:
        tasks.pop_task(tid)


def test_mixed_error_and_ok_is_terminal():
    good = tasks.new_task()
    bad = tasks.new_task()
    tasks.set_result(good, _ok_result("page one"))
    tasks.set_error(bad, "glare")
    try:
        out = collect_notebook_pages([good, bad])
        assert out["status"] == "done"
        assert out["pages"][0]["ok"] is True
        assert out["pages"][1]["ok"] is False
        assert out["pages"][1]["error"] == "glare"
        assert out["pages"][1]["full_text"] == ""
    finally:
        tasks.pop_task(good)
        tasks.pop_task(bad)


def test_expired_id_is_terminal():
    out = collect_notebook_pages(["deadbeefdead"])
    assert out["status"] == "done"
    assert out["pages"][0]["ok"] is False
    assert "expired" in out["pages"][0]["error"].lower()


def test_does_not_pop_tasks():
    tid = tasks.new_task()
    tasks.set_result(tid, _ok_result("still here"))
    try:
        collect_notebook_pages([tid])
        again = collect_notebook_pages([tid])
        assert again["pages"][0]["full_text"] == "still here"
        assert tasks.get_task(tid) is not None
    finally:
        tasks.pop_task(tid)


def test_one_pending_keeps_session_pending():
    done = tasks.new_task()
    pending = tasks.new_task("Transcribing…", 10)
    tasks.set_result(done, _ok_result("first"))
    try:
        out = collect_notebook_pages([done, pending])
        assert out["status"] == "pending"
        assert out["done"] == 1
        assert out["total"] == 2
    finally:
        tasks.pop_task(done)
        tasks.pop_task(pending)


def test_result_copy_buttons_call_page_helper():
    html = to_xml(notebook_session_result([
        {"n": 1, "ok": True, "full_text": "aaa", "processing_time": 1,
         "total_input_tokens": 1, "total_output_tokens": 1, "error": ""},
        {"n": 2, "ok": True, "full_text": "bbb", "processing_time": 1,
         "total_input_tokens": 1, "total_output_tokens": 1, "error": ""},
    ]))
    assert "copyCapText(this)" in html
    assert "copyCapText(this" in html and "cap-text-1" in html
    assert "}},2000)" not in html
    assert "navigator.clipboard" not in html


def test_capture_page_has_session_controls():
    with _client() as client:
        _login(client)
        r = client.get("/capture")
        assert r.status_code == 200
        body = r.text
        assert 'id="cap-next"' in body
        assert 'id="cap-done"' in body
        assert 'id="cap-pages"' in body
        assert "/process/notebook-page" in body
        assert "/process/notebook-ocr" not in body
        assert "Next page" in body
        assert "window.copyCapText" in body
        assert "--- page break ---" in body


def test_accept_page_requires_frame():
    with _client() as client:
        _login(client)
        r = client.post("/process/notebook-page")
        assert r.status_code == 400
        assert r.json()["ok"] is False


def test_session_status_requires_ids():
    with _client() as client:
        _login(client)
        r = client.get("/notebook-session-status")
        assert r.status_code == 400


def test_accept_page_and_read_result():
    fake = {
        "full_text": "standup notes",
        "method": "llm",
        "processing_time": 0.2,
        "total_input_tokens": 11,
        "total_output_tokens": 7,
    }
    with _client() as client:
        _login(client)
        with patch(
            "web_app.routes.capture.ocr_image_bytes",
            new_callable=AsyncMock,
            return_value=fake,
        ):
            r = client.post(
                "/process/notebook-page",
                files={"frame": ("capture.jpg", b"not-a-real-jpeg", "image/jpeg")},
            )
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["ok"] is True
            tid = data["task_id"]
            status = None
            for _ in range(40):
                status = client.get(f"/notebook-page-status/{tid}").json()
                if status["status"] in ("done", "error"):
                    break
                time.sleep(0.05)
            assert status["status"] == "done"
            session = client.get(f"/notebook-session-status?ids={tid}").json()
            assert session["status"] == "done"
            assert session["pages"][0]["full_text"] == "standup notes"
            html = client.get(f"/notebook-session-result?ids={tid}").text
            assert "standup notes" in html
            assert "📋 Copy" in html


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  ok  {fn.__name__}")
        except Exception as exc:
            failed += 1
            print(f" FAIL {fn.__name__}: {exc}")
    print(f"{len(tests) - failed}/{len(tests)} passed")
    raise SystemExit(1 if failed else 0)
