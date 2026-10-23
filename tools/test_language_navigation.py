#!/usr/bin/env python3
"""Check all language-switch links locally, optionally against GitHub Pages."""

from html.parser import HTMLParser
from pathlib import Path
import argparse
import time
from urllib.error import URLError
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://appsmakerdeluxe.github.io/tavolunio-privacy/"
LANGUAGES = ("de", "en", "es", "fr", "pt-br")
PAGES = ("index.html", *(f"{language}/index.html" for language in LANGUAGES))


class LanguageNavParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nav_depth = 0
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "nav":
            self.nav_depth += 1
        elif tag == "a" and self.nav_depth and "href" in attrs:
            self.links.append(attrs["href"])

    def handle_endtag(self, tag):
        if tag == "nav" and self.nav_depth:
            self.nav_depth -= 1


def parse_nav(html):
    parser = LanguageNavParser()
    parser.feed(html)
    return parser.links


def html_language(html):
    marker = '<html lang="'
    start = html.find(marker)
    if start < 0:
        raise AssertionError("missing html lang attribute")
    start += len(marker)
    return html[start:html.find('"', start)].lower()


def read_local(path):
    return (ROOT / path).read_text(encoding="utf-8")


def check_local():
    pages = {path: read_local(path) for path in PAGES}
    for source in PAGES:
        source_url = urljoin(BASE_URL, source.removesuffix("index.html"))
        hrefs = parse_nav(pages[source])
        if len(hrefs) != len(LANGUAGES):
            raise AssertionError(f"{source}: expected {len(LANGUAGES)} language links, got {len(hrefs)}")
        resolved = {urlparse(urljoin(source_url, href)).path for href in hrefs}
        expected = {urlparse(urljoin(BASE_URL, f"{language}/")).path for language in LANGUAGES}
        if resolved != expected:
            raise AssertionError(f"{source}: language links resolve outside the project site: {sorted(resolved)}")
        print(f"PASS: {source} links to all five language pages within the GitHub Pages project path")

    expected_html_languages = {"de": "de", "en": "en", "es": "es", "fr": "fr", "pt-br": "pt-br"}
    for language, expected in expected_html_languages.items():
        actual = html_language(pages[f"{language}/index.html"])
        if actual != expected:
            raise AssertionError(f"{language}: html lang is {actual}, expected {expected}")
    print("PASS: all localized pages declare their own language")

    retention_markers = {
        "de": "Bereinigungsjob ungefähr alle sechs Stunden",
        "en": "scheduled cleanup job checks approximately every six hours",
        "es": "un proceso de limpieza programado comprueba aproximadamente cada seis horas",
        "fr": "une tâche de nettoyage planifiée vérifie environ toutes les six heures",
        "pt-br": "uma tarefa de limpeza programada verifica aproximadamente a cada seis horas",
    }
    stale_markers = ("manually removed", "manuelle Löschung", "borrado manualmente", "suppression manuelle", "removido manualmente")
    for language, marker in retention_markers.items():
        content = pages[f"{language}/index.html"]
        if marker not in content:
            raise AssertionError(f"{language}: missing accurate scheduled room cleanup disclosure")
        if any(stale in content for stale in stale_markers):
            raise AssertionError(f"{language}: stale manual-only room cleanup claim remains")
    print("PASS: all five privacy translations describe scheduled room cleanup and no longer claim manual-only deletion")


def check_live():
    expected_urls = {language: urljoin(BASE_URL, f"{language}/") for language in LANGUAGES}

    def get_fresh(url):
        separator = "&" if "?" in url else "?"
        request_url = f"{url}{separator}language_test={time.time_ns()}"
        with urlopen(request_url, timeout=20) as response:
            return response.status, response.read().decode("utf-8")

    for source in PAGES:
        source_url = urljoin(BASE_URL, source.removesuffix("index.html"))
        _, html = get_fresh(source_url)
        hrefs = parse_nav(html)
        actual_urls = {language: urljoin(source_url, href) for language, href in zip(LANGUAGES, hrefs)}
        if len(hrefs) != len(LANGUAGES) or actual_urls != expected_urls:
            raise AssertionError(f"{source}: deployed language navigation resolves incorrectly: {actual_urls}")
        print(f"PASS: live {source} navigation targets all five project-local pages")

    for language, url in expected_urls.items():
        status, html = get_fresh(url)
        if status != 200:
            raise AssertionError(f"{url}: HTTP {status}")
        actual = html_language(html)
        if actual != language:
            raise AssertionError(f"{url}: served lang {actual}, expected {language}")
        print(f"PASS: live {language} page returns HTTP 200 and lang={actual}")
    print("PASS: every live language switch resolves to a page under this project")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="also follow every deployed language link")
    args = parser.parse_args()
    check_local()
    if args.live:
        check_live()


if __name__ == "__main__":
    main()
