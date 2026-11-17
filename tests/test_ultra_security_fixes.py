"""Regressions for public-only discovery, bounded bodies and report output."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sitemap_discovery
import agentic_check
import ucp_check
import url_safety


def test_declared_sitemap_cannot_use_the_operators_local_exception(monkeypatch):
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "127.0.0.1:3000")
    assert url_safety.validate_url_strict("http://127.0.0.1:3000/")
    with pytest.raises(url_safety.URLSafetyError):
        url_safety.validate_public_url_strict("http://127.0.0.1:3000/")
    with pytest.raises(url_safety.URLSafetyError):
        url_safety.safe_requests_get("http://127.0.0.1:3000/", public_only=True)

    @contextmanager
    def session(_url, *, public_only=False):
        assert public_only is True
        raise url_safety.URLSafetyError("public-only")
        yield

    monkeypatch.setattr(sitemap_discovery, "safe_requests_session", session)
    assert sitemap_discovery._bounded_fetch("http://127.0.0.1:3000/sitemap.xml", 100)["error"]


def test_ucp_operator_origin_is_local_but_other_hosts_remain_public_only(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv("CLAUDE_SEO_LOCAL_TARGETS", "127.0.0.1:3000,127.0.0.2:3000")
    seen = []
    def fetch(url, **kwargs):
        seen.append((url, kwargs["public_only"]))
        return SimpleNamespace(status_code=404, close=lambda: None)
    monkeypatch.setattr(ucp_check, "safe_requests_get", fetch)
    assert ucp_check.probe_endpoint("http://127.0.0.1:3000/admin")["error"].startswith("ssrf-blocked")
    assert ucp_check.audit_site("http://127.0.0.1:3000")["summary"].startswith("no-ucp-profile")
    assert ucp_check.probe_endpoint("http://127.0.0.1:3000/admin",
                                    operator_origin="http://127.0.0.1:3000")["reachable"]
    assert ucp_check.probe_endpoint("http://127.0.0.2:3000/admin",
                                    operator_origin="http://127.0.0.1:3000")["error"].startswith("ssrf-blocked")
    assert seen == [("http://127.0.0.1:3000/.well-known/ucp", False),
                    ("http://127.0.0.1:3000/admin", False)]


def test_ucp_status_probe_never_reads_the_body(monkeypatch):
    class Response:
        status_code = 200
        closed = False

        @property
        def content(self):
            pytest.fail("status probe read a hostile body")

        def close(self):
            self.closed = True

    response = Response()
    monkeypatch.setattr(ucp_check, "validate_public_url_strict", lambda url: (url, "93.184.216.34"))

    def fetch(_url, **kwargs):
        assert kwargs["public_only"] is True and kwargs["stream"] is True
        return response

    monkeypatch.setattr(ucp_check, "safe_requests_get", fetch)
    assert ucp_check.probe_endpoint("https://example.com/checkout")["reachable"] is True
    assert response.closed


def test_agentic_page_alternates_follow_operator_origin(monkeypatch):
    from types import SimpleNamespace

    seen = []

    def response(url, **kwargs):
        seen.append((url, kwargs["public_only"]))
        return SimpleNamespace(status_code=404, url=url, headers={},
                               raw=SimpleNamespace(read=lambda *a, **k: b""), close=lambda: None)

    monkeypatch.setattr(agentic_check, "safe_requests_get", response)
    agentic_check.audit_markdown("https://example.com/page", {
        "soup_links": {"markdown_alternates": ["http://127.0.0.1:3000/admin"]}})
    assert seen == [("https://example.com/page", False),
                    ("http://127.0.0.1:3000/admin", True),
                    ("https://example.com/page.md", False)]


def test_agentic_root_probes_keep_local_exception(monkeypatch):
    from types import SimpleNamespace
    root = "http://127.0.0.1:3000"
    seen = []
    def response(url, **kwargs):
        seen.append((url, kwargs["public_only"]))
        return SimpleNamespace(status_code=404, url=url, headers={},
                               raw=SimpleNamespace(read=lambda *a, **k: b""), close=lambda: None)
    monkeypatch.setattr(agentic_check, "safe_requests_get", response)
    agentic_check.audit_robots(root)
    agentic_check.audit_llms(root)
    agentic_check.audit_well_known(root)
    assert seen and all(url.startswith(root + "/") and public_only is False
                        for url, public_only in seen)


def test_safe_get_caps_decoded_bytes_and_closes_response(monkeypatch):
    class Response:
        closed = False

        def iter_content(self, chunk_size):
            yield b"1234"
            yield b"5678"

        def close(self):
            self.closed = True

    response = Response()

    @contextmanager
    def pin(*_a, **_kw):
        yield

    monkeypatch.setattr(url_safety, "validate_url_strict", lambda url: (url, "93.184.216.34"))
    monkeypatch.setattr(url_safety, "_validated_proxy_hosts", lambda *_a, **_kw: frozenset())
    monkeypatch.setattr(url_safety, "_pin_dns", pin)

    def fetch(_method, _url, **kwargs):
        assert kwargs["stream"] is True
        return response

    monkeypatch.setattr(url_safety, "_pinned_request", fetch)
    with pytest.raises(url_safety.ResponseTooLarge):
        url_safety.safe_requests_get("https://example.com/", max_bytes=5)
    assert response.closed


def test_dashboard_never_sends_brand_to_html_parser():
    html = (ROOT / "skills/seo-maps/assets/local-map-rank-dashboard.template.html").read_text()
    assert all("C.brand" not in line for line in html.splitlines() if "innerHTML" in line)
    assert "document.createTextNode(C.brand+\" (you)\")" in html


def test_pdf_removes_temporary_html_when_print_fails(tmp_path, monkeypatch):
    path = ROOT / "skills/seo-audit/report-template/build_pdf.py"
    spec = importlib.util.spec_from_file_location("build_pdf_regression", path)
    assert spec and spec.loader
    pdf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pdf)
    src = tmp_path / "report.html"
    src.write_text("<style>@media (max-width:900px){}@media (max-width:560px){}</style>"
                   '<div class="wrap">content</div>')

    def fail(*_a, **_kw):
        assert (tmp_path / "report.print.html").exists()
        raise subprocess.CalledProcessError(1, "fake chrome")

    monkeypatch.setattr(pdf.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        pdf.build(src, tmp_path / "report.pdf")
    assert not (tmp_path / "report.print.html").exists()
