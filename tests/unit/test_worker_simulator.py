import httpx

from vetglobal import worker_simulator


def test_worker_simulator_posts_success(monkeypatch, capsys) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}

    def fake_post(url: str, **kwargs: object) -> httpx.Response:
        captured.update(url=url, **kwargs)
        return httpx.Response(200, json={"status": "DONE"})

    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "worker-token-value")
    monkeypatch.setattr(worker_simulator.httpx, "post", fake_post)
    monkeypatch.setattr(
        "sys.argv",
        ["worker", "42", "--api-url", "http://api.example/", "--summary", "Stable"],
    )

    result = worker_simulator.main()

    assert result == 0
    assert captured["url"] == "http://api.example/internal/jobs/42/complete"
    assert captured["headers"] == {"X-Internal-Token": "worker-token-value"}
    assert captured["json"] == {"status": "DONE", "summary": "Stable"}
    assert '"DONE"' in capsys.readouterr().out
