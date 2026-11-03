# tests/test_browser.py
"""Elección del navegador para el respaldo de Google Maps."""
from pathlib import Path

import pytest

from backend.scraper.official import browser as browser_mod
from backend.scraper.official.browser import choose_browser

BRAVE_MAC = "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
CHROME_MAC = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


@pytest.fixture
def installed(monkeypatch):
    """Simula qué ejecutables existen en disco."""
    present: set[str] = set()
    real_exists = Path.exists

    def fake_exists(self):
        return str(self) in present or (real_exists(self) and str(self).startswith("/tmp"))
    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(browser_mod.shutil, "which", lambda cmd: None)
    return present


def test_auto_prefers_brave_on_macos(installed):
    installed.update({BRAVE_MAC, CHROME_MAC})
    choice = choose_browser("auto", "", platform="darwin")
    assert choice.enabled and choice.executable == BRAVE_MAC
    assert choice.label == "Brave"


def test_auto_falls_back_to_chrome(installed):
    installed.add(CHROME_MAC)
    assert choose_browser("auto", "", platform="darwin").executable == CHROME_MAC


def test_safari_is_not_controllable_and_uses_installed_chromium(installed):
    installed.add(BRAVE_MAC)
    choice = choose_browser("safari", "", platform="darwin")
    assert choice.executable == BRAVE_MAC
    assert "Safari no se puede controlar" in choice.note


def test_nothing_installed_falls_back_to_playwright_chromium(installed):
    choice = choose_browser("auto", "", platform="darwin")
    assert choice.enabled and choice.executable is None
    assert "No se encontró" in choice.note


def test_explicit_path_and_none(installed):
    installed.add("/opt/brave/brave")
    assert choose_browser("auto", "/opt/brave/brave").executable == "/opt/brave/brave"
    assert not choose_browser("auto", "/no/existe").enabled
    assert not choose_browser("none", "").enabled


def test_linux_uses_commands_on_path(monkeypatch):
    monkeypatch.setattr(browser_mod.shutil, "which",
                        lambda cmd: "/usr/bin/brave-browser" if cmd == "brave-browser" else None)
    monkeypatch.setattr(Path, "exists", lambda self: str(self) == "/usr/bin/brave-browser")
    assert choose_browser("brave", "", platform="linux").executable == "/usr/bin/brave-browser"


def test_windows_paths(monkeypatch):
    monkeypatch.setenv("PROGRAMFILES", r"C:\Program Files")
    paths = browser_mod.candidates("brave", platform="win32")
    assert any(p.endswith(r"BraveSoftware\Brave-Browser\Application\brave.exe") for p in paths)
