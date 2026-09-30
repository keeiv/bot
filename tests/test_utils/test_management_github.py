from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import Mock

import pytest

from src.services import management_service as module


class Response:
    def __init__(self, status=200, headers=None, data=None, text=""):
        self.status = status
        self.headers = headers or {}
        self.json = AsyncMock(return_value=data or [])
        self.text = AsyncMock(return_value=text)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


@pytest.fixture
def service(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module.time, "time", lambda: 1000.0)
    return module.ManagementService()


async def test_existing_token_used(service, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-only-token")
    try:
        session = await service.get_session()
        assert session.headers["Authorization"] == "Bearer test-only-token"
    finally:
        await service.close_session()


async def test_shared_cache_and_conditional_request(service, monkeypatch):
    data = [{"sha": "abc"}]
    session = SimpleNamespace(
        get=Mock(
            side_effect=[
                Response(headers={"ETag": "tag"}, data=data),
                Response(status=304),
            ]
        )
    )
    service.get_session = AsyncMock(return_value=session)
    assert await service._fetch_github_list("commits") == data
    assert await service._fetch_github_list("commits") == data
    assert session.get.call_count == 1
    monkeypatch.setattr(module.time, "time", lambda: 1301.0)
    assert await service._fetch_github_list("commits") == data
    assert session.get.call_args.kwargs["headers"] == {"If-None-Match": "tag"}


@pytest.mark.parametrize(
    "status,headers,text",
    [
        (403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "2000"}, ""),
        (429, {"Retry-After": "600"}, ""),
        (403, {}, "secondary rate limit exceeded"),
    ],
)
async def test_rate_limit_stops_other_endpoints(service, status, headers, text):
    session = SimpleNamespace(
        get=Mock(return_value=Response(status, headers, text=text))
    )
    service.get_session = AsyncMock(return_value=session)
    assert await service._fetch_github_list("commits") == []
    assert await service._fetch_github_list("pulls") == []
    assert session.get.call_count == 1
    assert service._github_retry_at >= 1060
    if headers.get("Retry-After"):
        assert service._github_retry_at >= 1600
    if headers.get("X-RateLimit-Reset"):
        assert service._github_retry_at > 2000


async def test_permission_denial_not_global_rate_limit(service):
    session = SimpleNamespace(
        get=Mock(return_value=Response(403, text="Resource not accessible"))
    )
    service.get_session = AsyncMock(return_value=session)
    await service._fetch_github_list("private")
    await service._fetch_github_list("private")
    assert session.get.call_count == 1
    assert service._github_retry_at == 0
    await service._fetch_github_list("other")
    assert session.get.call_count == 2


async def test_success_with_empty_quota_stops_next_request(service):
    session = SimpleNamespace(
        get=Mock(
            return_value=Response(
                200, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "2000"}
            )
        )
    )
    service.get_session = AsyncMock(return_value=session)
    await service._fetch_github_list("commits")
    await service._fetch_github_list("pulls")
    assert session.get.call_count == 1
