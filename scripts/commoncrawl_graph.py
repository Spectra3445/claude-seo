#!/usr/bin/env python3
"""
Common Crawl Web Graph parser for Claude SEO.

Downloads and parses Common Crawl's domain-level web graph ranking data to
extract PageRank, harmonic centrality, crawl/ranking presence, and host counts.
No API key needed (public data).

Data source: s3://commoncrawl/projects/hyperlinkgraph/
Releases: Monthly, each built from three crawls (cc-main-YYYY-mon-mon-mon)

Usage:
    python commoncrawl_graph.py example.com --json
    python commoncrawl_graph.py example.com --update --json
    python commoncrawl_graph.py --info --json
    python commoncrawl_graph.py example.com --release cc-main-2026-jul-aug-sep --json
"""

import argparse
import json
import os
import re
import sys
import time
from typing import NamedTuple, Optional

try:
    import requests
except ImportError:
    print("Error: requests library required. Install with: pip install requests")
    sys.exit(1)

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)
try:
    from backlinks_auth import get_cache_dir
    from google_auth import validate_url
except ImportError:
    print("Error: backlinks_auth.py and google_auth.py required in scripts/", file=sys.stderr)
    sys.exit(1)

# Common Crawl web graph base URL (HTTP access to S3 bucket)
CC_GRAPH_BASE = "https://data.commoncrawl.org/projects/hyperlinkgraph"

# Common Crawl's own list of published web graphs, newest first. Read at
# run time so a new release is picked up without editing this file.
CC_GRAPHINFO_URL = "https://index.commoncrawl.org/graphinfo.json"
MAX_DECOMPRESSED_BYTES = 2 * 1024 * 1024 * 1024
MAX_GZIP_LINE_CHARS = 1024 * 1024

# Fallback when graphinfo.json cannot be read (newest first).
# Naming convention: cc-main-YYYY-mon-mon-mon (lowercase month abbreviations).
# Common Crawl now publishes a graph every month from three consecutive
# crawls; this fallback keeps one release per quarter.
KNOWN_RELEASES = [
    "cc-main-2026-jul-aug-sep",
    "cc-main-2026-apr-may-jun",
    "cc-main-2026-jan-feb-mar",
    "cc-main-2025-oct-nov-dec",
    "cc-main-2025-jul-aug-sep",
    "cc-main-2025-apr-may-jun",
    "cc-main-2025-jan-feb-mar",
    "cc-main-2024-oct-nov-dec",
]

# Graph file types: filenames include the release name as prefix
# e.g., domain/cc-main-2026-jan-feb-mar-domain-vertices.txt.gz
VERTICES_SUFFIX = "-domain-vertices.txt.gz"
EDGES_SUFFIX = "-domain-edges.txt.gz"
RANKINGS_SUFFIX = "-domain-ranks.txt.gz"


def _graph_file_url(release: str, suffix: str) -> str:
    """Build the full URL for a CC web graph file."""
    return f"{CC_GRAPH_BASE}/{release}/domain/{release}{suffix}"


def _safe_float(s: str) -> Optional[float]:
    """Safely parse a float from a string, returning None on failure."""
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _published_releases(limit: int = 3) -> list:
    """Return up to `limit` release ids from graphinfo.json, newest first.

    Returns [] on any network or format problem, so callers fall back to
    KNOWN_RELEASES. Ids that fail _RELEASE_RE are skipped, because a release
    id is interpolated into a download URL and a cache path.
    """
    try:
        resp = requests.get(CC_GRAPHINFO_URL, timeout=10)
        resp.raise_for_status()
        graphs = resp.json()
    except (requests.exceptions.RequestException, ValueError):
        return []
    if not isinstance(graphs, list):
        return []
    releases = []
    for graph in graphs:
        release = graph.get("id") if isinstance(graph, dict) else None
        if isinstance(release, str) and _RELEASE_RE.match(release):
            releases.append(release)
        if len(releases) >= limit:
            break
    return releases


def _get_latest_release() -> Optional[str]:
    """
    Discover the latest available CC web graph release.

    Asks Common Crawl's graphinfo.json for the newest graph first, then
    falls back to KNOWN_RELEASES. Returns the first release whose domain
    vertices file exists.

    Returns:
        Release name (e.g., 'cc-main-2026-jul-aug-sep') or None.
    """
    for release in _published_releases() + KNOWN_RELEASES:
        url = _graph_file_url(release, VERTICES_SUFFIX)
        try:
            resp = requests.head(url, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                return release
        except requests.exceptions.RequestException:
            continue
    return None


_CACHE_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._-]")

# A Common Crawl release id, e.g. cc-main-2026-jan-feb-mar. Anchored, and no
# '..' anywhere, because this value lands in a filesystem path and a URL path.
# \Z, not $: $ also matches before a trailing newline.
_RELEASE_RE = re.compile(r"^(?!.*\.\.)[A-Za-z0-9._-]+\Z")


def _safe_cache_component(value: str) -> str:
    """Reduce one path component to a conservative charset.

    Everything outside [A-Za-z0-9._-] becomes '_', then any run of dots is
    collapsed so '..' can never survive. Both halves matter: stripping
    separators alone still lets '..' through on a caller that joins
    differently, and collapsing dots alone still lets a separator through.
    """
    cleaned = _CACHE_COMPONENT_RE.sub("_", value)
    while ".." in cleaned:
        cleaned = cleaned.replace("..", "_")
    return cleaned.strip("._") or "_"


def _get_cache_path(domain: str, release: str, data_type: str) -> str:
    """Get the cache file path for a domain's data.

    Both `domain` and `release` reach this from the CLI. `release` used to be
    interpolated raw, so `--release ../../../../tmp/x` escaped the cache
    directory and `_save_cache`'s open(..., "w") wrote outside it. Every
    component is now sanitised, and the joined result is asserted to stay
    inside the cache directory as defence in depth.
    """
    cache_dir = get_cache_dir()
    safe_domain = _safe_cache_component(domain)
    safe_release = _safe_cache_component(release)
    safe_type = _safe_cache_component(data_type)
    path = os.path.join(cache_dir, f"{safe_domain}-{safe_release}-{safe_type}.json")

    resolved = os.path.realpath(path)
    root = os.path.realpath(cache_dir)
    if not (resolved == root or resolved.startswith(root + os.sep)):
        raise ValueError(f"refusing to build a cache path outside {root}")
    return path


def _is_cached(domain: str, release: str) -> Optional[dict]:
    """Check if domain data is cached for a given release."""
    cache_path = _get_cache_path(domain, release, "combined")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r") as f:
                cached = json.load(f)
            # Check cache age (90 days max)
            cached_time = cached.get("metadata", {}).get("cached_at", 0)
            if time.time() - cached_time < 90 * 86400:
                return cached
        except (json.JSONDecodeError, IOError):
            pass
    return None


def _save_cache(domain: str, release: str, data: dict) -> None:
    """Save domain data to cache."""
    cache_path = _get_cache_path(domain, release, "combined")
    data.setdefault("metadata", {})["cached_at"] = time.time()
    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)


class GraphScanResult(NamedTuple):
    matches: list[list[str]]
    stop_reason: Optional[str] = None


def _stream_gz_chunked(url: str, target_domain: str, timeout: int = 120,
                        max_lines: int = 0) -> GraphScanResult:
    """
    Stream a gzipped file and filter for lines matching the target domain.

    Uses incremental zlib decompression to process large gzipped files
    without loading everything into memory. Stops early when enough matches
    are found.

    Args:
        url: URL of the gzipped file.
        target_domain: Domain to filter for (may be reversed, e.g., com.google).
        timeout: Request timeout in seconds.
        max_lines: Maximum matching lines to return (0 = unlimited).

    Returns:
        Matching lines and a stop reason when the scan was incomplete.
    """
    import zlib

    matches = []
    max_compressed_bytes = 500 * 1024 * 1024  # 500 MiB safety cap
    total_downloaded = 0
    total_decompressed = 0
    resp = None

    try:
        resp = requests.get(url, stream=True, timeout=timeout)
        resp.raise_for_status()

        # Incremental gzip decompression (wbits=16+MAX for gzip format)
        decompressor = zlib.decompressobj(zlib.MAX_WBITS | 16)
        leftover = ""

        for chunk in resp.iter_content(chunk_size=256 * 1024):  # 256 KiB chunks
            total_downloaded += len(chunk)
            if total_downloaded > max_compressed_bytes:
                return GraphScanResult(matches, "compressed graph limit reached")

            while chunk:
                decoded = decompressor.decompress(chunk, 1024 * 1024)
                chunk = decompressor.unconsumed_tail
                allowed = MAX_DECOMPRESSED_BYTES - total_decompressed
                capped = len(decoded) > allowed
                if capped:
                    decoded = decoded[:max(allowed, 0)]
                total_decompressed += len(decoded)
                text = decoded.decode("utf-8", errors="replace")
                lines = (leftover + text).split("\n")
                leftover = lines[-1]
                for line in lines[:-1]:
                    if len(line) > MAX_GZIP_LINE_CHARS:
                        return GraphScanResult(matches, "graph line limit reached")
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    fields = line.split("\t")
                    if any(field == target_domain or field.endswith(f".{target_domain}") for field in fields):
                        matches.append(fields)
                    if max_lines and len(matches) >= max_lines:
                        return GraphScanResult(matches)
                if capped:
                    return GraphScanResult(matches, "decompressed graph limit reached")
                if len(leftover) > MAX_GZIP_LINE_CHARS:
                    return GraphScanResult(matches, "graph line limit reached")

        if not decompressor.eof:
            return GraphScanResult(matches, "truncated graph stream")
    except (requests.exceptions.RequestException, zlib.error, MemoryError) as exc:
        return GraphScanResult(matches, f"graph stream failed ({type(exc).__name__})")
    finally:
        if resp is not None:
            resp.close()

    return GraphScanResult(matches)


def get_domain_metrics(domain: str, release: Optional[str] = None,
                       force_update: bool = False, timeout: int = 120,
                       top_referrers: int = 20) -> dict:
    """
    Get domain-level ranking metrics from Common Crawl web graph.

    Args:
        domain: Target domain (e.g., 'example.com').
        release: CC release name. Auto-detects latest if None.
        force_update: Force re-download, bypassing cache.
        timeout: Download timeout in seconds.
        top_referrers: Legacy no-op; referring domains are not extracted.

    Returns:
        Standard response dict with domain metrics.
    """
    # Clean domain
    domain = domain.lower().strip()
    if domain.lower().startswith("http"):
        if not validate_url(domain):
            return {
                "status": "error",
                "data": None,
                "error": f"Invalid or blocked URL: {domain}",
                "metadata": {"source": "commoncrawl"},
            }
        from urllib.parse import urlparse
        domain = urlparse(domain).netloc
    domain = domain.replace("www.", "")

    # Find release
    if not release:
        release = _get_latest_release()
        if not release:
            return {
                "status": "error",
                "data": None,
                "error": "Could not find any Common Crawl web graph release. Check connectivity.",
                "metadata": {"source": "commoncrawl"},
            }

    # Check cache
    if not force_update:
        cached = _is_cached(domain, release)
        if cached:
            data = cached.get("data")
            if isinstance(data, dict):
                data.pop("top_referring_domains", None)
                data.pop("referring_domains_sample", None)
            cached["metadata"]["from_cache"] = True
            return cached

    # Fetch rankings file (has PageRank + harmonic centrality + reversed domain names)
    # Format: harmonicc_pos \t harmonicc_val \t pr_pos \t pr_val \t host_rev \t n_hosts
    # Domains are reversed: com.google = google.com
    rankings_url = _graph_file_url(release, RANKINGS_SUFFIX)
    rankings_data = {}
    stop_reasons = []

    # Reverse domain for matching: google.com -> com.google
    reversed_domain = ".".join(reversed(domain.split(".")))

    try:
        ranking_scan = _stream_gz_chunked(rankings_url, reversed_domain,
                                          timeout=timeout, max_lines=5)
        if ranking_scan.stop_reason:
            stop_reasons.append(f"rankings: {ranking_scan.stop_reason}")
        for fields in ranking_scan.matches:
            if len(fields) >= 6:
                # fields[4] is the reversed hostname (e.g., com.google)
                if fields[4] == reversed_domain:
                    rankings_data = {
                        "harmonic_centrality_rank": int(fields[0]) if fields[0].isdigit() else None,
                        "harmonic_centrality": _safe_float(fields[1]),
                        "pagerank_rank": int(fields[2]) if fields[2].isdigit() else None,
                        "pagerank": _safe_float(fields[3]),
                        "n_hosts": int(fields[5]) if fields[5].isdigit() else None,
                    }
                    break
    except Exception as e:
        stop_reasons.append(f"rankings: {type(e).__name__}")

    # If not found in rankings, check vertices file to confirm domain was crawled at all
    in_rankings = bool(rankings_data)
    in_crawl = in_rankings  # If in rankings, definitely in crawl

    if not in_rankings:
        vertices_url = _graph_file_url(release, VERTICES_SUFFIX)
        try:
            vertex_scan = _stream_gz_chunked(vertices_url, reversed_domain,
                                             timeout=min(timeout, 60), max_lines=1)
            if vertex_scan.stop_reason:
                stop_reasons.append(f"vertices: {vertex_scan.stop_reason}")
            in_crawl = bool(vertex_scan.matches)
        except Exception as exc:
            stop_reasons.append(f"vertices: {type(exc).__name__}")

    # Build appropriate note based on what we found
    incomplete = bool(stop_reasons)
    if incomplete:
        note = "Graph scan incomplete; domain presence and metrics could not be confirmed."
    elif in_rankings:
        note = "Domain-level metrics from CC web graph. Quarterly updates."
    elif in_crawl:
        note = "Domain found in CC crawl but below ranking threshold (too small/new for PageRank rankings)."
    else:
        note = "Domain not found in Common Crawl data. It may be too new, too small, or not yet crawled."

    result = {
        "status": "partial" if incomplete else "success",
        "data": {
            "domain": domain,
            "in_crawl": in_crawl,
            "in_rankings": in_rankings,
            "pagerank": rankings_data.get("pagerank"),
            "pagerank_rank": rankings_data.get("pagerank_rank"),
            "harmonic_centrality": rankings_data.get("harmonic_centrality"),
            "harmonic_centrality_rank": rankings_data.get("harmonic_centrality_rank"),
            "n_hosts": rankings_data.get("n_hosts"),
            "note": note,
        },
        "error": None,
        "metadata": {
            "source": "commoncrawl",
            "release": release,
            "from_cache": False,
            "incomplete": incomplete,
            "stop_reason": "; ".join(stop_reasons) if incomplete else None,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }

    # Cache the result
    if not incomplete:
        _save_cache(domain, release, result)

    return result


def get_graph_info() -> dict:
    """
    Get information about available CC web graph releases and cache status.

    Returns:
        Standard response dict with release info.
    """
    latest = _get_latest_release()
    cache_dir = get_cache_dir()
    cached_files = []
    if os.path.exists(cache_dir):
        cached_files = [f for f in os.listdir(cache_dir) if f.endswith(".json")]

    return {
        "status": "success",
        "data": {
            "latest_release": latest,
            "known_releases": KNOWN_RELEASES,
            "cache_dir": cache_dir,
            "cached_files": len(cached_files),
            "cached_domains": [f.split("-cc-main")[0] for f in cached_files],
        },
        "error": None,
        "metadata": {
            "source": "commoncrawl",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Common Crawl Web Graph parser for Claude SEO"
    )
    parser.add_argument(
        "domain",
        nargs="?",
        default=None,
        help="Target domain to look up (e.g., example.com)",
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Show available releases and cache status",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Force re-download, bypassing cache",
    )
    parser.add_argument(
        "--release",
        default=None,
        help="Specific CC release to query (e.g., cc-main-2026-jan-feb-mar)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Download timeout in seconds (default: 120)",
    )
    parser.add_argument(
        "--top-referrers",
        type=int,
        default=20,
        help="Legacy no-op; referring domains are not extracted",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON",
    )

    args = parser.parse_args()

    if args.info:
        result = get_graph_info()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            data = result["data"]
            print("Common Crawl Web Graph Info")
            print(f"  Latest release: {data.get('latest_release', 'unknown')}")
            print(f"  Known releases: {', '.join(data.get('known_releases', []))}")
            print(f"  Cache dir:      {data.get('cache_dir', 'N/A')}")
            print(f"  Cached domains: {data.get('cached_files', 0)}")
        return

    if not args.domain:
        print("Error: domain argument required (or use --info)", file=sys.stderr)
        sys.exit(1)

    # Reject a malformed release rather than silently sanitising it. The value
    # is interpolated into both a cache filename and a download URL
    # (_graph_file_url), so quietly rewriting it for one and not the other
    # would make the cache key disagree with what was actually fetched.
    if args.release is not None and not _RELEASE_RE.match(args.release):
        print(
            f"Error: invalid --release {args.release!r}. Expected a release id "
            "such as cc-main-2026-jan-feb-mar (letters, digits, dot, dash, "
            "underscore only).",
            file=sys.stderr,
        )
        sys.exit(1)

    result = get_domain_metrics(
        domain=args.domain,
        release=args.release,
        force_update=args.update,
        timeout=args.timeout,
        top_referrers=args.top_referrers,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["status"] in ("success", "partial") and result["data"]:
            data = result["data"]
            cached = result.get("metadata", {}).get("from_cache", False)
            release = result.get("metadata", {}).get("release", "unknown")
            print(f"Common Crawl Domain Metrics: {data.get('domain', args.domain)}")
            print(f"  Release:                   {release} {'(cached)' if cached else ''}")
            print(f"  PageRank:                  {data.get('pagerank', 'N/A')} (rank #{data.get('pagerank_rank', 'N/A')})")
            print(f"  Harmonic Centrality:       {data.get('harmonic_centrality', 'N/A')} (rank #{data.get('harmonic_centrality_rank', 'N/A')})")
            print(f"  Number of hosts:           {data.get('n_hosts', 'N/A')}")
            if result["status"] == "partial":
                print(f"  Status:                    partial")
                print(f"  In crawl:                  {data.get('in_crawl')}")
                print(f"  Stopped:                   {result['metadata']['stop_reason']}")
        elif result.get("error"):
            print(f"Error: {result['error']}", file=sys.stderr)
    return 2 if result["status"] == "partial" else 0


if __name__ == "__main__":
    sys.exit(main())
