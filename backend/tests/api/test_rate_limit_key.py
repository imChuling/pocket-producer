"""Rate-limit buckets are per signed-in user, falling back to the forwarded IP."""

from types import SimpleNamespace

from api.deps import _rate_limit_key


def _request(headers: dict, client_host: str | None = "10.0.0.1"):
    return SimpleNamespace(
        headers=headers,
        client=SimpleNamespace(host=client_host) if client_host else None,
    )


def test_two_users_behind_one_nat_get_separate_buckets():
    shared_ip = {"X-Forwarded-For": "203.0.113.7, 10.1.1.1"}
    a = _rate_limit_key(_request({**shared_ip, "Authorization": "Bearer " + "a" * 40}))
    b = _rate_limit_key(_request({**shared_ip, "Authorization": "Bearer " + "b" * 40}))
    assert a != b
    assert a.startswith("user:") and b.startswith("user:")


def test_same_token_maps_to_the_same_bucket_without_storing_it():
    token = "Bearer " + "secret-token-" * 4
    key = _rate_limit_key(_request({"Authorization": token}))
    assert key == _rate_limit_key(_request({"Authorization": token}))
    assert "secret" not in key


def test_anonymous_requests_key_on_first_forwarded_ip():
    key = _rate_limit_key(_request({"X-Forwarded-For": "203.0.113.7, 10.1.1.1"}))
    assert key == "ip:203.0.113.7"


def test_anonymous_without_proxy_header_uses_client_host():
    assert _rate_limit_key(_request({})) == "ip:10.0.0.1"
    assert _rate_limit_key(_request({}, client_host=None)) == "ip:unknown"
