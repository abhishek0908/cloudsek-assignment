import pytest
from unittest.mock import patch
from app.core.security import validate_ssrf
from app.core.exceptions import SSRFBlockedError


class TestValidateSSRF:

    @patch("app.core.security.socket.gethostbyname")
    def test_private_ip_blocked(self, mock_gethostbyname):
        mock_gethostbyname.return_value = "10.0.0.1"
        with pytest.raises(SSRFBlockedError):
            validate_ssrf("http://internal.example.com")

    @patch("app.core.security.socket.gethostbyname")
    def test_loopback_ip_blocked(self, mock_gethostbyname):
        mock_gethostbyname.return_value = "127.0.0.1"
        with pytest.raises(SSRFBlockedError):
            validate_ssrf("http://localhost")

    @patch("app.core.security.socket.gethostbyname")
    def test_link_local_ip_blocked(self, mock_gethostbyname):
        mock_gethostbyname.return_value = "169.254.169.254"
        with pytest.raises(SSRFBlockedError):
            validate_ssrf("http://metadata.internal")

    @patch("app.core.security.socket.gethostbyname")
    def test_public_ip_allowed(self, mock_gethostbyname):
        mock_gethostbyname.return_value = "93.184.216.34"
        assert validate_ssrf("http://example.com") is None
