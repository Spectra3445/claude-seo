from scripts import host_variants


def test_host_variant_probe_reports_www_and_http_with_injected_fetcher():
    class Response:
        def __init__(self, status, headers=None):
            self.status_code = status
            self.headers = headers or {}

        def close(self):
            pass

    def fetch(url, **kwargs):
        if url.startswith("http://"):
            return Response(301, {"location": url.replace("http://", "https://")})
        return Response(200)

    findings = host_variants.probe_host_variants("https://example.com/", fetch)
    ids = [f["id"] for f in findings]
    assert "www-host-not-redirected" in ids
    assert "http-not-redirected" not in ids


def test_host_variant_probe_treats_challenge_as_unknown():
    class Response:
        status_code = 403
        headers = {}

        def close(self):
            pass

    findings = host_variants.probe_host_variants("https://example.com/", lambda *a, **kw: Response())
    assert findings == []
