"""
Tests for scripts/commoncrawl_graph.py.

Focus: cache-path construction. `--release` reached `_get_cache_path`
completely unsanitised and the result is opened for writing in `_save_cache`,
so `--release ../../../../tmp/x` wrote outside the cache directory. The same
value is also interpolated into a download URL by `_graph_file_url`, so it is
rejected at the CLI boundary rather than silently rewritten -- otherwise the
cache key would disagree with what was actually fetched.

No network: only the pure path/validation helpers are exercised.
"""

from __future__ import annotations

import gzip
import os
import sys

import pytest

_SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

pytest.importorskip("requests")
import commoncrawl_graph as ccg  # noqa: E402


def _inside_cache_dir(path: str) -> bool:
    root = os.path.realpath(ccg.get_cache_dir())
    resolved = os.path.realpath(path)
    return resolved == root or resolved.startswith(root + os.sep)


# ---------------------------------------------------------------------------
# path traversal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "domain,release",
    [
        ("example.com", "../../../../tmp/pwned"),
        ("example.com", ".."),
        ("../../../../tmp/evil", "cc-main-2026-jan-feb-mar"),
        ("../..", ".."),
        ("example.com/../../etc", "cc-main-2026-jan-feb-mar"),
    ],
)
def test_cache_path_never_escapes_the_cache_dir(domain, release):
    assert _inside_cache_dir(ccg._get_cache_path(domain, release, "combined"))


def test_cache_path_preserves_legitimate_values():
    """Sanitising must not mangle real inputs, or every cache miss forever."""
    path = ccg._get_cache_path("example.com", "cc-main-2026-jan-feb-mar", "combined")
    assert os.path.basename(path) == "example.com-cc-main-2026-jan-feb-mar-combined.json"
    assert _inside_cache_dir(path)


def test_safe_cache_component_collapses_dot_runs_and_separators():
    assert ".." not in ccg._safe_cache_component("../../etc/passwd")
    assert "/" not in ccg._safe_cache_component("a/b/c")
    assert os.sep not in ccg._safe_cache_component("a\\b")
    # Never returns empty, which would produce a path like "-release-type.json".
    assert ccg._safe_cache_component("...") != ""
    assert ccg._safe_cache_component("") != ""


# ---------------------------------------------------------------------------
# release validation (also guards the URL built by _graph_file_url)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "release",
    ["cc-main-2026-jan-feb-mar", "cc-main-2024-oct-nov-dec", "CC-MAIN-2024-33", "a_b.c-1"],
)
def test_release_pattern_accepts_real_release_ids(release):
    assert ccg._RELEASE_RE.match(release)


@pytest.mark.parametrize(
    "release",
    ["../../../../tmp/pwned", "..", "a/../b", "a..b", "with space", "", "a/b", "x\ty", "x\n"],
)
def test_release_pattern_rejects_traversal_and_junk(release):
    assert not ccg._RELEASE_RE.match(release)


# ---------------------------------------------------------------------------
# latest-release discovery (graphinfo.json first, KNOWN_RELEASES fallback)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self, status=200, payload=None, exc=None):
        self.status_code = status
        self._payload = payload
        self._exc = exc

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ccg.requests.exceptions.HTTPError(str(self.status_code))

    def json(self):
        if self._exc:
            raise self._exc
        return self._payload


def _head_ok_for(existing):
    def head(url, **_kw):
        return _Resp(200 if any(f"/{r}/domain/" in url for r in existing) else 404)
    return head


def test_latest_release_prefers_graphinfo(monkeypatch):
    graphs = [{"id": "cc-main-2099-jan-feb-mar"}, {"id": ccg.KNOWN_RELEASES[0]}]
    monkeypatch.setattr(ccg.requests, "get", lambda url, **kw: _Resp(payload=graphs))
    monkeypatch.setattr(ccg.requests, "head", _head_ok_for({"cc-main-2099-jan-feb-mar"}))
    assert ccg._get_latest_release() == "cc-main-2099-jan-feb-mar"


def test_latest_release_skips_unsafe_graphinfo_ids(monkeypatch):
    graphs = [{"id": "../../etc/passwd"}, {"id": 42}, "junk", {"id": "cc-main-2099-jan-feb-mar"}]
    monkeypatch.setattr(ccg.requests, "get", lambda url, **kw: _Resp(payload=graphs))
    assert ccg._published_releases() == ["cc-main-2099-jan-feb-mar"]


@pytest.mark.parametrize(
    "response",
    [_Resp(status=503), _Resp(payload={"not": "a list"}), _Resp(exc=ValueError("bad json"))],
)
def test_latest_release_falls_back_to_known_releases(monkeypatch, response):
    monkeypatch.setattr(ccg.requests, "get", lambda url, **kw: response)
    monkeypatch.setattr(ccg.requests, "head", _head_ok_for(set(ccg.KNOWN_RELEASES)))
    assert ccg._get_latest_release() == ccg.KNOWN_RELEASES[0]


def test_latest_release_falls_back_when_graphinfo_unreachable(monkeypatch):
    def boom(url, **kw):
        raise ccg.requests.exceptions.ConnectionError("offline")

    monkeypatch.setattr(ccg.requests, "get", boom)
    monkeypatch.setattr(ccg.requests, "head", _head_ok_for({ccg.KNOWN_RELEASES[1]}))
    assert ccg._get_latest_release() == ccg.KNOWN_RELEASES[1]


def test_gzip_graph_caps_decoded_bytes_and_closes_stream(monkeypatch):
    class Stream:
        closed = False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield gzip.compress(b"x" * 1000 + b"\ncom.example\t1\n")

        def close(self):
            self.closed = True

    stream = Stream()
    monkeypatch.setattr(ccg.requests, "get", lambda *_a, **_kw: stream)
    monkeypatch.setattr(ccg, "MAX_DECOMPRESSED_BYTES", 64)
    result = ccg._stream_gz_chunked("https://data.commoncrawl.org/graph.gz", "com.example")
    assert result.matches == []
    assert result.stop_reason == "decompressed graph limit reached"
    assert stream.closed


def test_incomplete_graph_scan_is_reported_and_never_cached(monkeypatch):
    monkeypatch.setattr(ccg, "_stream_gz_chunked", lambda *_a, **_kw: ccg.GraphScanResult(
        [], "decompressed graph limit reached"))
    monkeypatch.setattr(ccg, "_save_cache", lambda *_a: pytest.fail("incomplete result cached"))
    result = ccg.get_domain_metrics("example.com", release="cc-main-2026-nov", force_update=True)
    assert result["status"] == "partial"
    assert result["metadata"]["incomplete"] is True
    assert result["data"]["in_crawl"] is False
    assert "incomplete" in result["data"]["note"]


def test_cap_preserves_exact_rank_row_and_partial_metrics(monkeypatch):
    import zlib
    row = b"1\t2.5\t3\t0.8\tcom.example\t7\n"
    compressor = zlib.compressobj(wbits=zlib.MAX_WBITS | 16)
    chunks = [compressor.compress(row) + compressor.flush(zlib.Z_SYNC_FLUSH),
              compressor.compress(b"x" * 1000) + compressor.flush(zlib.Z_FINISH)]
    class Stream:
        def raise_for_status(self):
            pass
        def iter_content(self, chunk_size):
            yield from chunks
        def close(self):
            pass
    monkeypatch.setattr(ccg.requests, "get", lambda *_a, **_kw: Stream())
    monkeypatch.setattr(ccg, "MAX_DECOMPRESSED_BYTES", len(row) + 16)
    monkeypatch.setattr(ccg, "_save_cache", lambda *_a: pytest.fail("partial rank cached"))
    result = ccg.get_domain_metrics("example.com", release="cc-main-2026-nov", force_update=True)
    assert result["status"] == "partial"
    assert result["data"]["in_rankings"] is True
    assert result["data"]["pagerank"] == 0.8
    assert "decompressed graph limit" in result["metadata"]["stop_reason"]


def test_text_cli_prints_partial_metrics_and_reason(monkeypatch, capsys):
    monkeypatch.setattr(ccg, "get_domain_metrics", lambda **_kw: {
        "status": "partial", "data": {"domain": "example.com", "pagerank": 0.8,
        "in_crawl": True, "pagerank_rank": 3},
        "metadata": {"release": "cc-main-2026-nov", "stop_reason": "rankings: decompressed graph limit reached"},
        "error": None})
    monkeypatch.setattr(sys, "argv", ["commoncrawl_graph.py", "example.com"])
    assert ccg.main() == 2
    output = capsys.readouterr().out
    assert "PageRank:" in output and "0.8" in output
    assert "Status:" in output and "partial" in output
    assert "Stopped:" in output and "decompressed graph limit" in output


def test_gzip_graph_still_reads_matching_lines(monkeypatch):
    class Stream:
        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield gzip.compress(b"com.example\t1\ncom.other\t2\n")

        def close(self):
            pass

    monkeypatch.setattr(ccg.requests, "get", lambda *_a, **_kw: Stream())
    assert ccg._stream_gz_chunked("https://data.commoncrawl.org/graph.gz", "com.example").matches == [["com.example", "1"]]
