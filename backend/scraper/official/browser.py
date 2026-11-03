"""Navegador para el respaldo de Google Maps.

El scraping de fuentes oficiales es HTTP puro: no necesita navegador. Solo el
respaldo opcional de ubicación en Google Maps abre uno, con Playwright.

En vez de descargar el Chromium de Playwright se usa un navegador basado en
Chromium que ya esté instalado (Brave, Chrome, Edge o Chromium). Safari no es
posible: Playwright solo controla motores Chromium, Firefox y su propio WebKit,
no la app Safari.

    SCRAPER_BROWSER       auto (por defecto) | brave | chrome | edge | chromium |
                          playwright (Chromium descargado por Playwright) | none
    SCRAPER_BROWSER_PATH  ruta exacta del ejecutable (tiene prioridad)

Uso desde la terminal (lo usa run.sh):

    python -m backend.scraper.official.browser          # muestra el elegido
"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ...config import config

SUPPORTED = ("brave", "chrome", "edge", "chromium")


def _mac(app: str, binary: str) -> list[str]:
    return [f"/Applications/{app}.app/Contents/MacOS/{binary}",
            str(Path.home() / f"Applications/{app}.app/Contents/MacOS/{binary}")]


def _win(*relative: str) -> list[str]:
    roots = [os.environ.get(v) for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    return [str(Path(root) / rel) for root in roots if root for rel in relative]


def candidates(name: str, platform: str = sys.platform) -> list[str]:
    """Rutas posibles del navegador ``name`` en la plataforma dada."""
    if platform == "darwin":
        return {
            "brave": _mac("Brave Browser", "Brave Browser"),
            "chrome": _mac("Google Chrome", "Google Chrome"),
            "edge": _mac("Microsoft Edge", "Microsoft Edge"),
            "chromium": _mac("Chromium", "Chromium"),
        }[name]
    if platform.startswith("win"):
        return {
            "brave": _win(r"BraveSoftware\Brave-Browser\Application\brave.exe"),
            "chrome": _win(r"Google\Chrome\Application\chrome.exe"),
            "edge": _win(r"Microsoft\Edge\Application\msedge.exe"),
            "chromium": _win(r"Chromium\Application\chrome.exe"),
        }[name]
    commands = {
        "brave": ("brave-browser", "brave", "brave-browser-stable"),
        "chrome": ("google-chrome", "google-chrome-stable"),
        "edge": ("microsoft-edge", "microsoft-edge-stable"),
        "chromium": ("chromium", "chromium-browser"),
    }[name]
    return [p for p in (shutil.which(c) for c in commands) if p]


@dataclass
class BrowserChoice:
    executable: Optional[str]   # None → Chromium descargado por Playwright
    label: str
    enabled: bool = True
    note: str = ""


def choose_browser(browser: Optional[str] = None, browser_path: Optional[str] = None,
                   platform: str = sys.platform) -> BrowserChoice:
    browser = (browser if browser is not None else config.browser).strip().lower() or "auto"
    browser_path = browser_path if browser_path is not None else config.browser_path

    if browser == "none":
        return BrowserChoice(None, "ninguno", enabled=False)
    if browser_path:
        if Path(browser_path).exists():
            return BrowserChoice(browser_path, browser_path)
        return BrowserChoice(None, "ninguno", enabled=False,
                             note=f"SCRAPER_BROWSER_PATH no existe: {browser_path}")
    if browser == "playwright":
        return BrowserChoice(None, "Chromium de Playwright")

    note = ""
    if browser == "safari":
        note = ("Safari no se puede controlar con Playwright; "
                "se usa el primer navegador Chromium instalado (Brave, Chrome, Edge).")
        browser = "auto"
    if browser not in SUPPORTED and browser != "auto":
        note = f"SCRAPER_BROWSER={browser} no es válido; se usa la detección automática."
        browser = "auto"

    for name in (SUPPORTED if browser == "auto" else (browser,)):
        for path in candidates(name, platform):
            if Path(path).exists():
                return BrowserChoice(path, name.capitalize(), note=note)

    wanted = "Brave, Chrome, Edge ni Chromium" if browser == "auto" else browser.capitalize()
    return BrowserChoice(None, "Chromium de Playwright",
                         note=(note + " " if note else "")
                         + f"No se encontró {wanted}; se intentará el Chromium de Playwright.")


if __name__ == "__main__":
    choice = choose_browser()
    if choice.note:
        print(choice.note, file=sys.stderr)
    if not choice.enabled:
        print("ninguno")
        sys.exit(1)
    print(choice.executable or "playwright")
