"""系统 DNS 解析失败时的备用解析（DNS over HTTPS）。

背景：在海外网络下，系统解析器经常解析不了经多层国内 CDN 转接的行情域名
（新浪行情、北交所等），而域名本身是正常的。浏览器自带解析通道所以不受影响，
Python 走系统解析器就会得到 ``[Errno 8] nodename nor servname provided``。

做法：包一层 ``socket.getaddrinfo``。系统解析成功时完全不介入；只有系统解析
抛出 ``socket.gaierror`` 时，才通过 HTTPS 向公共解析服务查询 A 记录，并把结果
交还给调用方。连接和 TLS 校验仍然使用原始域名，证书校验不受影响。

可用环境变量 ``LITCHI_DNS_FALLBACK=0`` 关闭。
"""

from __future__ import annotations

import http.client
import ipaddress
import json
import logging
import os
import socket
import ssl
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

logger = logging.getLogger("utils.dns_fallback")

# (连接地址, 路径, 额外请求头)。用 IP 直连，避免备用解析自身依赖系统 DNS。
DOH_ENDPOINTS: tuple[tuple[str, str, dict[str, str]], ...] = (
    ("223.5.5.5", "/resolve", {}),  # 阿里公共 DNS
    ("1.1.1.1", "/dns-query", {"accept": "application/dns-json"}),  # Cloudflare
)
DOH_TIMEOUT_SECONDS = 3.0
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 600
NEGATIVE_TTL_SECONDS = 30

Fetcher = Callable[[str], tuple[list[str], int]]
EventHook = Callable[[str, float, str | None], None]
_GetAddrInfo = Callable[..., list[Any]]


@dataclass(frozen=True)
class FallbackStats:
    system_failures: int
    resolved: int
    unresolved: int
    hosts: tuple[str, ...]


def parse_doh_answer(payload: object) -> tuple[list[str], int]:
    """从 DoH JSON 响应里取出 IPv4 地址和可缓存秒数；格式不对一律视为无结果。"""
    if not isinstance(payload, dict) or payload.get("Status") != 0:
        return [], NEGATIVE_TTL_SECONDS
    addresses: list[str] = []
    ttl = MAX_TTL_SECONDS
    answers = payload.get("Answer")
    for answer in answers if isinstance(answers, list) else []:
        if not isinstance(answer, dict) or answer.get("type") != 1:
            continue
        data = answer.get("data")
        try:
            address = ipaddress.IPv4Address(str(data))
        except ValueError:
            continue
        # 公共解析被污染时可能返回保留地址；这类结果不能交给调用方去连接。
        if address.is_private or address.is_loopback or address.is_unspecified:
            continue
        addresses.append(str(address))
        raw_ttl = answer.get("TTL")
        if isinstance(raw_ttl, int) and not isinstance(raw_ttl, bool):
            ttl = min(ttl, raw_ttl)
    if not addresses:
        return [], NEGATIVE_TTL_SECONDS
    return addresses, max(MIN_TTL_SECONDS, min(MAX_TTL_SECONDS, ttl))


def _tls_context() -> ssl.SSLContext:
    """优先用 certifi 的根证书：独立发行的 Python 在 macOS 上不一定带系统证书。"""
    try:
        import certifi  # noqa: PLC0415

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def doh_fetch(host: str) -> tuple[list[str], int]:
    """依次询问各公共解析服务，返回第一个非空结果。"""
    for address, path, headers in DOH_ENDPOINTS:
        connection = http.client.HTTPSConnection(
            address, timeout=DOH_TIMEOUT_SECONDS, context=_tls_context()
        )
        try:
            connection.request("GET", f"{path}?name={quote(host)}&type=A", headers=headers)
            response = connection.getresponse()
            if response.status != 200:
                continue
            addresses, ttl = parse_doh_answer(json.loads(response.read(65536)))
            if addresses:
                return addresses, ttl
        except (OSError, ValueError, http.client.HTTPException):
            logger.debug("DoH endpoint failed: %s host=%s", address, host, exc_info=True)
        finally:
            connection.close()
    return [], NEGATIVE_TTL_SECONDS


def _eligible(host: object) -> str | None:
    """只对普通域名启用；IP、本机名和单标签主机名交回系统处理。"""
    if isinstance(host, bytes):
        try:
            host = host.decode("ascii")
        except UnicodeDecodeError:
            return None
    if not isinstance(host, str):
        return None
    name = host.rstrip(".").lower()
    if not name or "." not in name or name == "localhost" or name.endswith(".local"):
        return None
    try:
        ipaddress.ip_address(name)
    except ValueError:
        return name
    return None


class DnsFallback:
    """带缓存的备用解析器；``getaddrinfo`` 可直接替换 ``socket.getaddrinfo``。"""

    def __init__(
        self,
        system_getaddrinfo: _GetAddrInfo,
        *,
        fetcher: Fetcher = doh_fetch,
        on_event: EventHook | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._system = system_getaddrinfo
        self._fetcher = fetcher
        self._on_event = on_event
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[float, list[str]]] = {}
        self._system_failures = 0
        self._resolved = 0
        self._unresolved = 0
        self._hosts: set[str] = set()

    def set_event_hook(self, on_event: EventHook | None) -> None:
        self._on_event = on_event

    def stats(self) -> FallbackStats:
        with self._lock:
            return FallbackStats(
                self._system_failures, self._resolved, self._unresolved,
                tuple(sorted(self._hosts)),
            )

    def lookup(self, host: str) -> list[str]:
        now = self._clock()
        with self._lock:
            cached = self._cache.get(host)
            if cached and cached[0] > now:
                return list(cached[1])
        started = time.monotonic()
        addresses, ttl = self._fetcher(host)
        elapsed_ms = (time.monotonic() - started) * 1000
        with self._lock:
            self._cache[host] = (self._clock() + ttl, list(addresses))
            first_time = host not in self._hosts
            if addresses:
                self._resolved += 1
                self._hosts.add(host)
            else:
                self._unresolved += 1
        if addresses and first_time:
            logger.warning(
                "系统 DNS 解析失败，已改用备用解析: host=%s addresses=%s", host, addresses
            )
        elif not addresses:
            logger.warning("系统 DNS 与备用解析均失败: host=%s", host)
        if self._on_event is not None:
            try:
                self._on_event(host, elapsed_ms, None if addresses else "备用解析无结果")
            except Exception:
                logger.debug("DNS fallback event hook failed", exc_info=True)
        return addresses

    def getaddrinfo(self, host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        try:
            return self._system(host, port, *args, **kwargs)
        except socket.gaierror as error:
            name = _eligible(host)
            if name is None:
                raise
            with self._lock:
                self._system_failures += 1
            results: list[Any] = []
            for address in self.lookup(name):
                try:
                    results.extend(self._system(address, port, *args, **kwargs))
                except socket.gaierror:
                    continue  # 调用方只要 IPv6 等情形：这条地址不适用
            if not results:
                raise error from None
            return results


_installed: DnsFallback | None = None
_install_lock = threading.Lock()


def install(on_event: EventHook | None = None) -> DnsFallback | None:
    """进程内只安装一次；关闭时返回 None，不改动 ``socket.getaddrinfo``。"""
    global _installed
    with _install_lock:
        if _installed is not None:
            if on_event is not None:
                _installed.set_event_hook(on_event)
            return _installed
        if os.environ.get("LITCHI_DNS_FALLBACK", "1").strip().lower() in {
            "0", "false", "off", "no"
        }:
            logger.info("备用域名解析已通过 LITCHI_DNS_FALLBACK 关闭")
            return None
        fallback = DnsFallback(socket.getaddrinfo, on_event=on_event)
        socket.getaddrinfo = fallback.getaddrinfo  # type: ignore[assignment]
        _installed = fallback
        logger.info("备用域名解析已启用：仅在系统 DNS 失败时使用")
        return fallback


def installed() -> DnsFallback | None:
    return _installed
