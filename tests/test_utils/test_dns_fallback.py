"""备用域名解析：只在系统解析失败时介入，结果缓存，失败不掩盖原始错误。"""

import socket

import pytest

from src.utils import dns_fallback
from src.utils.dns_fallback import DnsFallback, parse_doh_answer

ADDRINFO = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("36.51.224.96", 443))]


class FakeSystem:
    """系统解析器替身：指定域名解析失败，IP 字面量和其他域名正常。"""

    def __init__(self, failing: set[str]):
        self.failing = failing
        self.calls: list[str] = []

    def __call__(self, host, port, *args, **kwargs):
        self.calls.append(host)
        if str(host).rstrip(".").lower() in self.failing:
            raise socket.gaierror(8, "nodename nor servname provided, or not known")
        if kwargs.get("family") == socket.AF_INET6 and "." in str(host):
            raise socket.gaierror(-9, "Address family for hostname not supported")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (host, port))]


def test_system_success_never_touches_fallback():
    fetched: list[str] = []
    fallback = DnsFallback(FakeSystem(set()), fetcher=lambda h: (fetched.append(h) or [], 60))
    assert fallback.getaddrinfo("push2.eastmoney.com", 443)[0][4] == ("push2.eastmoney.com", 443)
    assert fetched == [] and fallback.stats().system_failures == 0


def test_system_failure_uses_fallback_addresses_and_records_event():
    events: list[tuple[str, str | None]] = []
    system = FakeSystem({"hq.sinajs.cn"})
    fallback = DnsFallback(
        system,
        fetcher=lambda host: (["36.51.224.96", "36.51.224.97"], 120),
        on_event=lambda host, ms, error: events.append((host, error)),
    )
    result = fallback.getaddrinfo("hq.sinajs.cn", 443, type=socket.SOCK_STREAM)
    assert [item[4] for item in result] == [("36.51.224.96", 443), ("36.51.224.97", 443)]
    assert events == [("hq.sinajs.cn", None)]
    stats = fallback.stats()
    assert (stats.system_failures, stats.resolved, stats.hosts) == (1, 1, ("hq.sinajs.cn",))


def test_fallback_result_is_cached_until_ttl_expires():
    now = [0.0]
    fetches: list[str] = []

    def fetcher(host):
        fetches.append(host)
        return ["36.51.224.96"], 60

    fallback = DnsFallback(FakeSystem({"hq.sinajs.cn"}), fetcher=fetcher, clock=lambda: now[0])
    fallback.getaddrinfo("hq.sinajs.cn", 443)
    fallback.getaddrinfo("HQ.sinajs.cn.", 443)  # 大小写与末尾点号归一
    assert fetches == ["hq.sinajs.cn"]
    now[0] = 61.0
    fallback.getaddrinfo("hq.sinajs.cn", 443)
    assert len(fetches) == 2


def test_original_error_is_raised_when_fallback_has_no_answer():
    events: list[str | None] = []
    fallback = DnsFallback(
        FakeSystem({"no-such-host.example.com"}),
        fetcher=lambda host: ([], 30),
        on_event=lambda host, ms, error: events.append(error),
    )
    with pytest.raises(socket.gaierror) as caught:
        fallback.getaddrinfo("no-such-host.example.com", 443)
    assert caught.value.errno == 8
    assert events == ["备用解析无结果"] and fallback.stats().unresolved == 1


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1", "printer", "mac.local", None])
def test_ip_literals_and_local_names_are_left_to_the_system(host):
    def system(host, port, *args, **kwargs):
        raise socket.gaierror(8, "not known")

    fetched: list[str] = []
    fallback = DnsFallback(system, fetcher=lambda h: (fetched.append(h) or ["1.2.3.4"], 60))
    with pytest.raises(socket.gaierror):
        fallback.getaddrinfo(host, 80)
    assert fetched == []


def test_ipv6_only_request_keeps_original_error():
    fallback = DnsFallback(FakeSystem({"hq.sinajs.cn"}), fetcher=lambda h: (["36.51.224.96"], 60))
    with pytest.raises(socket.gaierror) as caught:
        fallback.getaddrinfo("hq.sinajs.cn", 443, family=socket.AF_INET6)
    assert caught.value.errno == 8


def test_event_hook_failure_does_not_break_resolution():
    def broken(host, ms, error):
        raise RuntimeError("stats unavailable")

    fallback = DnsFallback(
        FakeSystem({"hq.sinajs.cn"}), fetcher=lambda h: (["36.51.224.96"], 60), on_event=broken
    )
    assert fallback.getaddrinfo("hq.sinajs.cn", 443)


def test_parse_doh_answer_keeps_public_ipv4_and_clamps_ttl():
    payload = {"Status": 0, "Answer": [
        {"type": 5, "data": "idc-hq-hk.sinajs.cn.", "TTL": 5},
        {"type": 1, "data": "36.51.224.96", "TTL": 5},
        {"type": 1, "data": "49.7.37.144", "TTL": 9999},
    ]}
    assert parse_doh_answer(payload) == (["36.51.224.96", "49.7.37.144"], 60)


@pytest.mark.parametrize("payload", [
    None, [], {"Status": 3}, {"Status": 0}, {"Status": 0, "Answer": "x"},
    {"Status": 0, "Answer": [{"type": 1, "data": "not-an-ip"}]},
    {"Status": 0, "Answer": [{"type": 1, "data": "127.0.0.1"}, {"type": 1, "data": "10.0.0.8"}]},
    {"Status": 0, "Answer": [{"type": 28, "data": "2400:89c0::1"}]},
])
def test_parse_doh_answer_rejects_malformed_or_unusable_responses(payload):
    assert parse_doh_answer(payload) == ([], dns_fallback.NEGATIVE_TTL_SECONDS)


def test_install_is_disabled_by_environment(monkeypatch):
    monkeypatch.setenv("LITCHI_DNS_FALLBACK", "0")
    monkeypatch.setattr(dns_fallback, "_installed", None)
    original = socket.getaddrinfo
    assert dns_fallback.install() is None
    assert socket.getaddrinfo is original


def test_install_patches_once_and_can_be_restored(monkeypatch):
    monkeypatch.setenv("LITCHI_DNS_FALLBACK", "1")
    monkeypatch.setattr(dns_fallback, "_installed", None)
    original = socket.getaddrinfo
    monkeypatch.setattr(socket, "getaddrinfo", original)  # 测试结束自动还原
    first = dns_fallback.install()
    assert first is not None and socket.getaddrinfo == first.getaddrinfo
    assert dns_fallback.install() is first
