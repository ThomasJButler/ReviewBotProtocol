"""GitHub App auth and client against a fake api.github.com served by respx."""

import json
import time

import httpx
import jwt
import pytest
import respx

from services.github_app_auth import InstallationTokenProvider
from services.github_client import GitHubClient, GitHubError
from tests.conftest import TEST_PRIVATE_KEY

BASE = "https://api.github.com"
TOKEN_JSON = {"token": "t", "expires_at": "2099-01-01T00:00:00Z"}


def _provider(http=None):
    return InstallationTokenProvider("123456", TEST_PRIVATE_KEY, 555, base_url=BASE, http=http)


def _token_route():
    return respx.post(f"{BASE}/app/installations/555/access_tokens").mock(return_value=httpx.Response(201, json=TOKEN_JSON))


@respx.mock
async def test_installation_token_is_minted_with_an_app_jwt_and_cached():
    route = respx.post(f"{BASE}/app/installations/555/access_tokens").mock(
        return_value=httpx.Response(201, json={"token": "ghs_new", "expires_at": "2099-01-01T00:00:00Z"}))
    p = _provider()
    assert await p.token() == "ghs_new"
    assert await p.token() == "ghs_new"
    assert route.call_count == 1
    auth = route.calls[0].request.headers["Authorization"]
    assert auth.startswith("Bearer ")
    from cryptography.hazmat.primitives import serialization
    pub = serialization.load_pem_private_key(TEST_PRIVATE_KEY.encode(), None).public_key()
    claims = jwt.decode(auth[7:], pub, algorithms=["RS256"])
    assert claims["iss"] == "123456" and claims["exp"] - claims["iat"] <= 600


@respx.mock
async def test_expired_token_is_refetched_after_401():
    respx.post(f"{BASE}/app/installations/555/access_tokens").mock(
        side_effect=[httpx.Response(201, json={"token": "ghs_one", "expires_at": "2099-01-01T00:00:00Z"}),
                     httpx.Response(201, json={"token": "ghs_two", "expires_at": "2099-01-01T00:00:00Z"})])
    pull = respx.get(f"{BASE}/repos/octocat/repo/pulls/42").mock(
        side_effect=[httpx.Response(401, json={"message": "Bad credentials"}), httpx.Response(200, json={"number": 42})])
    async with httpx.AsyncClient() as http:
        client = GitHubClient(_provider(http), BASE, http=http)
        assert (await client.get_pull("octocat/repo", 42))["number"] == 42
    assert pull.calls[1].request.headers["Authorization"] == "token ghs_two"


@respx.mock
async def test_pr_files_are_paginated_with_per_page_on_every_page():
    def page(n):
        return [{"filename": f"f{n}_{i}.py", "status": "modified", "additions": 1, "deletions": 0, "changes": 1, "patch": "+x"} for i in range(100)]
    _token_route()
    base = f"{BASE}/repos/octocat/repo/pulls/42/files"
    route = respx.get(base).mock(side_effect=lambda req: httpx.Response(
        200, json=page(int(req.url.params.get("page", "1"))),
        headers={"Link": f'<{base}?page=2>; rel="next"'} if req.url.params.get("page", "1") == "1" else {}))
    async with httpx.AsyncClient() as http:
        files, truncated = await GitHubClient(_provider(http), BASE, http=http).list_pull_files("octocat/repo", 42)
    assert len(files) == 200 and truncated is False
    assert all(c.request.url.params.get("per_page") == "100" for c in route.calls)


@respx.mock
async def test_page_cap_is_reported_as_truncation():
    from services import github_client as gc
    _token_route()
    base = f"{BASE}/repos/octocat/repo/pulls/42/files"
    respx.get(base).mock(side_effect=lambda req: httpx.Response(
        200, json=[{"filename": "a.py", "status": "modified", "patch": "+x"}] * 100, headers={"Link": f'<{base}?page=9>; rel="next"'}))
    original = gc.MAX_FILES_PAGES
    gc.MAX_FILES_PAGES = 2
    try:
        async with httpx.AsyncClient() as http:
            files, truncated = await GitHubClient(_provider(http), BASE, http=http).list_pull_files("octocat/repo", 42)
    finally:
        gc.MAX_FILES_PAGES = original
    assert len(files) == 200 and truncated is True


@respx.mock
async def test_link_to_another_host_is_refused_with_the_token_unsent():
    _token_route()
    base = f"{BASE}/repos/octocat/repo/pulls/42/files"
    respx.get(base).mock(return_value=httpx.Response(200, json=[], headers={"Link": '<https://evil.example/steal>; rel="next"'}))
    evil = respx.get("https://evil.example/steal").mock(return_value=httpx.Response(200, json=[]))
    async with httpx.AsyncClient() as http:
        with pytest.raises(GitHubError) as e:
            await GitHubClient(_provider(http), BASE, http=http).list_pull_files("octocat/repo", 42)
    assert "evil.example" in str(e.value) and not evil.called


@respx.mock
async def test_redirect_is_not_treated_as_success():
    _token_route()
    respx.get(f"{BASE}/repos/octocat/old/pulls/42").mock(return_value=httpx.Response(301, headers={"Location": f"{BASE}/repos/octocat/new/pulls/42"}))
    async with httpx.AsyncClient() as http:  # no follow_redirects, like an injected client
        with pytest.raises(GitHubError) as e:
            await GitHubClient(_provider(http), BASE, http=http).get_pull("octocat/old", 42)
    assert e.value.status == 301


@respx.mock
async def test_rate_limit_backs_off_using_reset_header():
    _token_route()
    route = respx.get(f"{BASE}/repos/octocat/repo/pulls/42").mock(side_effect=[
        httpx.Response(403, json={"message": "API rate limit exceeded"}, headers={"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(int(time.time()) + 1)}),
        httpx.Response(200, json={"number": 42})])
    async with httpx.AsyncClient() as http:
        assert (await GitHubClient(_provider(http), BASE, http=http).get_pull("octocat/repo", 42))["number"] == 42
    assert route.call_count == 2


@respx.mock
async def test_forbidden_without_rate_limit_headers_raises_immediately():
    _token_route()
    route = respx.get(f"{BASE}/repos/octocat/repo/pulls/42").mock(return_value=httpx.Response(403, json={"message": "Resource not accessible by integration"}))
    async with httpx.AsyncClient() as http:
        with pytest.raises(GitHubError) as e:
            await GitHubClient(_provider(http), BASE, http=http).get_pull("octocat/repo", 42)
    assert e.value.status == 403 and route.call_count == 1


@respx.mock
async def test_review_is_posted_as_one_comment_review():
    _token_route()
    route = respx.post(f"{BASE}/repos/octocat/repo/pulls/42/reviews").mock(return_value=httpx.Response(200, json={"id": 9, "html_url": "https://github.com/octocat/repo/pull/42#pullrequestreview-9"}))
    async with httpx.AsyncClient() as http:
        out = await GitHubClient(_provider(http), BASE, http=http).create_pull_review(
            "octocat/repo", 42, "a" * 40, "body", [{"path": "app.py", "line": 2, "side": "RIGHT", "body": "note"}])
    sent = json.loads(route.calls[0].request.content)
    assert sent == {"commit_id": "a" * 40, "body": "body", "event": "COMMENT", "comments": [{"path": "app.py", "line": 2, "side": "RIGHT", "body": "note"}]}
    assert out["html_url"].startswith("https://github.com/")
    assert route.calls[0].request.headers["User-Agent"] == "ReviewBot-Protocol"


@respx.mock
async def test_rejected_inline_comments_fall_back_to_body_only_with_sanitised_paths():
    _token_route()
    route = respx.post(f"{BASE}/repos/octocat/repo/pulls/42/reviews").mock(
        side_effect=[httpx.Response(422, json={"message": "Unprocessable Entity", "errors": [{"message": "Pull request review thread line must be part of the diff"}]}),
                     httpx.Response(200, json={"id": 10})])
    async with httpx.AsyncClient() as http:
        await GitHubClient(_provider(http), BASE, http=http).create_pull_review(
            "octocat/repo", 42, "a" * 40, "body", [{"path": "a`b\n@everyone.py", "line": 99, "side": "RIGHT", "body": "note"}])
    second = json.loads(route.calls[1].request.content)
    assert "comments" not in second and "could not be attached inline" in second["body"]
    assert "a`b" not in second["body"] and "\n@everyone" not in second["body"]


@respx.mock
async def test_other_422s_are_final():
    _token_route()
    route = respx.post(f"{BASE}/repos/octocat/repo/pulls/42/reviews").mock(
        return_value=httpx.Response(422, json={"message": "Validation Failed", "errors": ["You have exceeded a secondary rate limit"]}))
    async with httpx.AsyncClient() as http:
        with pytest.raises(GitHubError):
            await GitHubClient(_provider(http), BASE, http=http).create_pull_review(
                "octocat/repo", 42, "a" * 40, "body", [{"path": "app.py", "line": 2, "side": "RIGHT", "body": "note"}])
    assert route.call_count == 1


@respx.mock
async def test_other_errors_raise():
    _token_route()
    respx.get(f"{BASE}/repos/octocat/repo/pulls/42").mock(return_value=httpx.Response(404, json={"message": "Not Found"}))
    async with httpx.AsyncClient() as http:
        with pytest.raises(GitHubError) as e:
            await GitHubClient(_provider(http), BASE, http=http).get_pull("octocat/repo", 42)
    assert e.value.status == 404


@respx.mock
async def test_installation_tokens_are_scoped_to_the_repository_and_two_permissions():
    from services.github_app_auth import REVIEW_PERMISSIONS
    route = respx.post(f"{BASE}/app/installations/555/access_tokens").mock(return_value=httpx.Response(201, json={
        "token": "ghs_scoped", "expires_at": "2099-01-01T00:00:00Z", "permissions": dict(REVIEW_PERMISSIONS)}))
    async with httpx.AsyncClient() as http:
        provider = InstallationTokenProvider("123456", TEST_PRIVATE_KEY, 555, base_url=BASE, http=http, repository="octocat/repo")
        assert await provider.token() == "ghs_scoped"
    import json
    body = json.loads(route.calls.last.request.content)
    assert body == {"repositories": ["repo"], "permissions": {"pull_requests": "write", "metadata": "read"}}


@respx.mock
async def test_a_token_wider_than_requested_is_refused():
    respx.post(f"{BASE}/app/installations/555/access_tokens").mock(return_value=httpx.Response(201, json={
        "token": "ghs_wide", "expires_at": "2099-01-01T00:00:00Z",
        "permissions": {"pull_requests": "write", "metadata": "read", "contents": "write"}}))
    async with httpx.AsyncClient() as http:
        provider = InstallationTokenProvider("123456", TEST_PRIVATE_KEY, 555, base_url=BASE, http=http, repository="octocat/repo")
        with pytest.raises(RuntimeError, match="wider permissions"):
            await provider.token()


@respx.mock
async def test_a_refused_scope_explains_which_permission_is_missing():
    respx.post(f"{BASE}/app/installations/555/access_tokens").mock(return_value=httpx.Response(422, json={"message": "no"}))
    async with httpx.AsyncClient() as http:
        provider = InstallationTokenProvider("123456", TEST_PRIVATE_KEY, 555, base_url=BASE, http=http, repository="octocat/repo")
        with pytest.raises(RuntimeError, match="pull_requests:write"):
            await provider.token()


def test_the_app_jwt_lives_five_minutes_and_allows_clock_skew():
    import jwt as pyjwt
    provider = InstallationTokenProvider("123456", TEST_PRIVATE_KEY, 555, base_url=BASE)
    claims = pyjwt.decode(provider.app_jwt(), options={"verify_signature": False})
    assert claims["iss"] == "123456" and claims["exp"] - claims["iat"] == 360, "5 minutes plus the 60 s skew allowance"
