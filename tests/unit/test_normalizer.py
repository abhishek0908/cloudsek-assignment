import pytest
from app.core.normalizer import normalize_url


class TestNormalizeUrl:

    def test_lowercases_and_strips_www(self):
        assert normalize_url("HTTP://WWW.Example.Com") == "http://example.com/"

    def test_removes_default_ports(self):
        assert normalize_url("http://example.com:80") == "http://example.com/"
        assert normalize_url("https://example.com:443") == "https://example.com/"

    def test_preserves_non_default_port(self):
        assert normalize_url("http://example.com:8080") == "http://example.com:8080/"

    def test_adds_trailing_slash_for_root(self):
        assert normalize_url("http://example.com") == "http://example.com/"

    def test_preserves_path_strips_trailing_slash(self):
        assert normalize_url("http://example.com/path/") == "http://example.com/path"

    def test_strips_query_and_fragment(self):
        assert normalize_url("http://example.com/path?q=1#h") == "http://example.com/path"

    def test_ip_address_host(self):
        assert normalize_url("http://93.184.216.34") == "http://93.184.216.34/"

    def test_handles_full_chain(self):
        result = normalize_url("HTTPS://WWW.example.com:443/api/v1/data/")
        assert result == "https://example.com/api/v1/data"
