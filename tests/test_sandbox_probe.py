from types import SimpleNamespace

from app.sandbox_probe import verify_source_urls


class FakeProcess:
    def code_run(self, code: str, timeout: int):
        assert "https://example.com/report" in code
        assert timeout == 20
        return SimpleNamespace(
            exit_code=0,
            result='[{"url":"https://example.com/report","reachable":true,"status":200,"final_url":"https://example.com/report"}]',
        )


class FakeClient:
    def __init__(self):
        self.deleted = False
        self.sandbox = SimpleNamespace(process=FakeProcess())

    def create(self, timeout: int):
        assert timeout == 60
        return self.sandbox

    def delete(self, sandbox):
        assert sandbox is self.sandbox
        self.deleted = True


def test_verifies_untrusted_sources_in_disposable_sandbox() -> None:
    client = FakeClient()
    rows = verify_source_urls(["https://example.com/report"], client=client)
    assert rows[0]["reachable"] is True
    assert client.deleted is True


def test_rejects_non_http_urls_before_sandbox() -> None:
    client = FakeClient()
    assert verify_source_urls(["file:///etc/passwd", "javascript:alert(1)"], client=client) == []
