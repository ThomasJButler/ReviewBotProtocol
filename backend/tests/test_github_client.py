"""GitHub client behaviour against a fake api.github.com (respx). No network."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx


@pytest.fixture
def gh():
    from services.github_client import GitHubClient
    c = GitHubClient(installation_id=555)
    c._get_access_token = AsyncMock(return_value="ghs_testtoken")
    return c


@respx.mock
async def test_status_check_posts_to_the_commit(gh):
    route = respx.post("https://api.github.com/repos/octocat/repo/statuses/" + "a" * 40).mock(
        return_value=httpx.Response(201, json={"id": 1, "state": "pending"}))
    await gh.create_status_check("octocat/repo", "a" * 40, "pending", "working", context="reviewbot-protocol/review")
    assert route.called
    sent = json.loads(route.calls[0].request.content)
    assert sent["state"] == "pending"
    assert sent["context"] == "reviewbot-protocol/review"
    assert route.calls[0].request.headers["Authorization"] == "token ghs_testtoken"


@respx.mock
async def test_review_comment_is_posted_with_line_and_sha(gh):
    route = respx.post("https://api.github.com/repos/octocat/repo/pulls/42/comments").mock(
        return_value=httpx.Response(201, json={"id": 99}))
    await gh.post_review_comment("octocat/repo", 42, "body", "a" * 40, "app.py", 12)
    sent = json.loads(route.calls[0].request.content)
    assert sent == {"body": "body", "commit_id": "a" * 40, "path": "app.py", "line": 12, "side": "RIGHT"}


@pytest.mark.xfail(strict=True, reason="SR: get_pr_files fetches one page of 30; must paginate")
@respx.mock
async def test_pr_files_are_paginated(gh):
    def page(n):
        return [{"filename": f"f{n}_{i}.py", "status": "modified", "additions": 1, "deletions": 0, "changes": 1,
                 "blob_url": "", "raw_url": "", "contents_url": "", "patch": "+x"} for i in range(100)]
    base = "https://api.github.com/repos/octocat/repo/pulls/42/files"
    respx.get(base).mock(side_effect=lambda req: httpx.Response(
        200, json=page(int(req.url.params.get("page", "1"))),
        headers={"Link": f'<{base}?page=2>; rel="next"'} if req.url.params.get("page", "1") == "1" else {}))
    files = await gh.get_pr_files("octocat/repo", 42)
    assert len(files) == 200


@pytest.mark.xfail(strict=True, reason="SR-08: installation token minting uses a PyGithub API that does not exist; replaced by services.github_app_auth")
@respx.mock
async def test_installation_token_is_minted_with_app_jwt():
    from services.github_app_auth import InstallationTokenProvider
    route = respx.post("https://api.github.com/app/installations/555/access_tokens").mock(
        return_value=httpx.Response(201, json={"token": "ghs_new", "expires_at": "2099-01-01T00:00:00Z"}))
    provider = InstallationTokenProvider(app_id="123456", private_key_pem=_test_rsa_key(), installation_id=555)
    tok = await provider.token()
    assert tok == "ghs_new"
    assert route.calls[0].request.headers["Authorization"].startswith("Bearer ")


def _test_rsa_key() -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption()).decode()
