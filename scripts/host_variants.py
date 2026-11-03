#!/usr/bin/env python3
"""Read-only check for HTTP and www host variants."""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urljoin, urlsplit

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
from snapshot_io import finding, write_json  # noqa: E402
from url_safety import safe_requests_get  # noqa: E402

BLOCKED = {401, 403, 429, 999}
MAX_HOPS = 5


def probe_host_variants(origin: str, fetcher=None) -> list[dict]:
    fetcher = fetcher or safe_requests_get
    canonical = urlsplit(origin)
    apex = (canonical.hostname or "").removeprefix("www.")
    www = "www." + apex
    variants = (
        [f"http://{www}/", f"https://{apex}/"]
        if canonical.hostname and canonical.hostname.lower().startswith("www.")
        else [f"http://{apex}/", f"http://{www}/", f"https://{www}/"]
    )
    observations = []
    issues = []
    canonical_url = f"{canonical.scheme}://{canonical.netloc}/"
    for variant in variants:
        current, hops, unknown = variant, 0, False
        try:
            for hops in range(MAX_HOPS + 1):
                response = fetcher(current, timeout=8, allow_redirects=False)
                status = response.status_code
                headers = {str(k).lower(): v for k, v in response.headers.items()}
                if hasattr(response, "close"):
                    response.close()
                if status in BLOCKED or "cf-mitigated" in headers:
                    unknown = True
                    break
                if 300 <= status < 400:
                    location = headers.get("location")
                    if not location or hops == MAX_HOPS:
                        break
                    current = urljoin(current, location)
                    continue
                if 200 <= status < 300:
                    observations.append(
                        {"url": variant, "status": status, "final_url": current, "hops": hops}
                    )
                break
        except Exception:
            unknown = True
        if unknown:
            continue
        if hops > 1 and _canonical_host(current) == _canonical_host(canonical_url):
            issues.append(
                finding(
                    "host-redirect-chain", "Low", "Host variant uses a multi-hop redirect chain",
                    [variant], details=[{"variant": variant, "hops": hops, "final_url": current}],
                )
            )
        if variant.startswith("http://") and any(row["url"] == variant and row["hops"] == 0 for row in observations):
            issues.append(
                finding(
                    "http-not-redirected", "Medium", "HTTP host variant does not redirect to HTTPS",
                    [variant], details=[{"variant": variant, "hops": hops, "final_url": current}],
                )
            )
    nonwww = next(
        (row for row in observations if urlsplit(row["final_url"]).hostname == apex and row["status"] == 200),
        None,
    )
    withwww = next(
        (row for row in observations if urlsplit(row["final_url"]).hostname == www and row["status"] == 200),
        None,
    )
    if nonwww and withwww:
        issues.append(
            finding(
                "www-host-not-redirected", "Medium", "Both www and non-www hosts serve the site",
                [withwww["url"]], details=[{"variant": withwww["url"], "hops": withwww["hops"], "final_url": withwww["final_url"]}],
            )
        )
    return issues


def _canonical_host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--out", default="-")
    args = parser.parse_args()
    result = {
        "check": "host-variants",
        "source": {"url": args.url},
        "findings": probe_host_variants(args.url),
    }
    write_json(result, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
