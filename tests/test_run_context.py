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


def test_start_mutation_run_carries_manager_context_issue(monkeypatch):
    server = load_server(monkeypatch)
    server.AGENT_ID = "agent-1"
    server.MANAGER_CONTEXT_ISSUE_ID = "manager-context-issue"
    captured = {}

    async def fake_post(path, body=None):
        captured.update(path=path, body=body)
        return {"id": "run-123"}

    async def fake_get(path, params=None):
        return {"status": "running"}

    monkeypatch.setattr(server, "_post", fake_post)
    monkeypatch.setattr(server, "_get", fake_get)

    result = asyncio.run(server._start_mutation_run())

    assert result == "run-123"
    assert captured == {
        "path": "/agents/agent-1/heartbeat/invoke",
        "body": {
            "payload": {
                "issueId": "manager-context-issue",
                "mutation": "mcp_manager",
            },
            "reason": "mcp_manager_mutation",
            "triggerDetail": "system",
        },
    }


def test_issue_scope_rejects_issue_outside_allowed_project(monkeypatch):
    server = load_server(monkeypatch)
    server.ALLOWED_PROJECT_ID = "betty-project"

    async def fake_get(path, params=None):
        return {"id": "issue-1", "identifier": "TAA-870", "projectId": "other-project"}

    monkeypatch.setattr(server, "_get", fake_get)

    result = asyncio.run(server._ensure_issue_scope("TAA-870"))

    assert result["isError"] is True
    assert "allowed project" in result["message"]


def test_wildcard_issue_scope_allows_any_project(monkeypatch):
    server = load_server(monkeypatch)
    server.ALLOWED_PROJECT_ID = "*"

    async def fake_get(path, params=None):
        return {"id": "issue-1", "identifier": "TAA-878", "projectId": "other-project"}

    monkeypatch.setattr(server, "_get", fake_get)

    result = asyncio.run(server._ensure_issue_scope("TAA-878"))

    assert result is None


def test_wildcard_create_project_scope_allows_any_project(monkeypatch):
    server = load_server(monkeypatch)
    server.ALLOWED_PROJECT_ID = "*"

    assert server._ensure_create_project_scope("any-project") is None
