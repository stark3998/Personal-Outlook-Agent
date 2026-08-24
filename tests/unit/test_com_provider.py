"""Tests for the Windows COM provider (no live Outlook required)."""

from __future__ import annotations

from outlook_agent.config import ProviderKind, Settings
from outlook_agent.domain import ProviderName
from outlook_agent.providers.outlook.com.executor import ComError, ComErrorType, ComExecutor
from outlook_agent.providers.outlook.com.provider import OutlookCOMProvider, _dt
from outlook_agent.providers.outlook.factory import build_provider


class _UnavailableExec:
    """A COM executor stand-in that reports the environment as unusable."""

    available = False

    async def version(self) -> str | None:
        return None

    async def is_running(self) -> bool:
        return False


def test_provider_name_exists() -> None:
    assert ProviderName.OUTLOOK_COM.value == "outlook.com"


def test_capabilities_empty_when_unavailable() -> None:
    provider = OutlookCOMProvider(_UnavailableExec())
    assert provider.capabilities().supported == frozenset()


async def test_probe_outlook_unavailable() -> None:
    provider = OutlookCOMProvider(_UnavailableExec())
    info = await provider.probe_outlook()
    assert info.installed is False
    assert info.running is False


async def test_probe_permissions_unavailable() -> None:
    provider = OutlookCOMProvider(_UnavailableExec())
    perms = await provider.probe_permissions()
    assert perms.automation is False


def test_executor_available_is_bool() -> None:
    assert isinstance(ComExecutor().available, bool)


def test_dt_rejects_sentinel_years() -> None:
    class _Fake:
        year, month, day, hour, minute, second = 4501, 1, 1, 0, 0, 0

    assert _dt(_Fake()) is None
    assert _dt(None) is None


def test_com_error_carries_type() -> None:
    err = ComError("boom", ComErrorType.NOT_INSTALLED)
    assert err.error_type is ComErrorType.NOT_INSTALLED


def test_factory_builds_com_provider() -> None:
    provider = build_provider(Settings(provider=ProviderKind.COM))
    assert isinstance(provider, OutlookCOMProvider)
