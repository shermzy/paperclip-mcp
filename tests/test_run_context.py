import asyncio
import importlib


def load_server(monkeypatch):
    monkeypatch.setenv("PAPERCLIP_API_KEY", "test-key")
    monkeypatch.setenv("PAPERCLIP_COMPANY_ID", "test-company")
    monkeypatch.setenv("PAPERCLIP_HEARTBEAT_WEBHOOK_SECRET", "test-secret")
    return importlib.import_module("paperclip_mcp.server")


def test_headers_only_include_real_run_id(monkeypatch):
    server = load_server(monkeypatch)

    assert "X-Paperclip-Run-Id" not in server._headers()
    assert server._headers("run-123")["X-Paperclip-Run-Id"] == "run-123"


def test_mutation_attaches_run_id(monkeypatch):
    server = load_server(monkeypatch)
    captured = {}

    async def fake_start():
        return "run-123"

    async def fake_request(method, path, *, body=None, run_id=None, **kwargs):
        captured.update(method=method, path=path, body=body, run_id=run_id)
        return {"ok": True}

    async def fake_finish(run_id):
        captured["finished"] = run_id

    monkeypatch.setattr(server, "_start_mutation_run", fake_start)
    monkeypatch.setattr(server, "_request", fake_request)
    monkeypatch.setattr(server, "_finish_mutation_run", fake_finish)

    result = asyncio.run(server._mutate("PATCH", "/issues/TAA-810", body={"status": "done"}))

    assert result == {"ok": True}
    assert captured == {
        "method": "PATCH",
        "path": "/issues/TAA-810",
        "body": {"status": "done"},
        "run_id": "run-123",
        "finished": "run-123",
    }
