import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src/alibabacloud_apsaradb_for_mongodb_mcp_server"))

from utils import mask_connection_string, validate_connection_string, _is_private_ip


class TestMaskConnectionString:
    def test_masks_password(self):
        conn = "mongodb://admin:secretpass@host.mongodb.rds.aliyuncs.com:3717/test"
        result = mask_connection_string(conn)
        assert "secretpass" not in result
        assert "admin:***@" in result

    def test_masks_complex_password(self):
        conn = "mongodb://root:p@ss:w0rd!@host.mongodb.rds.aliyuncs.com:3717/db"
        result = mask_connection_string(conn)
        assert "p@ss:w0rd!" not in result
        assert "***@" in result

    def test_no_credentials(self):
        conn = "mongodb://host.mongodb.rds.aliyuncs.com:3717/test"
        result = mask_connection_string(conn)
        assert result == conn


class TestIsPrivateIp:
    @pytest.mark.parametrize("ip", [
        "127.0.0.1",
        "10.0.0.1",
        "10.255.255.255",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.1.1",
        "169.254.169.254",
    ])
    def test_private_ips(self, ip):
        assert _is_private_ip(ip) is True

    @pytest.mark.parametrize("ip", [
        "8.8.8.8",
        "1.1.1.1",
        "172.32.0.1",
        "11.0.0.1",
    ])
    def test_public_ips(self, ip):
        assert _is_private_ip(ip) is False

    def test_hostname_returns_false(self):
        assert _is_private_ip("example.com") is False


class TestValidateConnectionString:
    def test_allows_aliyun_mongodb_rds(self):
        conn = "mongodb://root:pass@dds-abc123.mongodb.rds.aliyuncs.com:3717/admin"
        validate_connection_string(conn)

    def test_allows_aliyun_mongodb(self):
        conn = "mongodb://root:pass@dds-abc123.mongodb.aliyuncs.com:3717/admin"
        validate_connection_string(conn)

    def test_rejects_private_ip_127(self):
        conn = "mongodb://root:pass@127.0.0.1:27017/admin"
        with pytest.raises(ValueError, match="private/internal"):
            validate_connection_string(conn)

    def test_rejects_private_ip_10(self):
        conn = "mongodb://root:pass@10.0.0.5:27017/admin"
        with pytest.raises(ValueError, match="private/internal"):
            validate_connection_string(conn)

    def test_rejects_private_ip_172(self):
        conn = "mongodb://root:pass@172.16.0.1:27017/admin"
        with pytest.raises(ValueError, match="private/internal"):
            validate_connection_string(conn)

    def test_rejects_private_ip_192(self):
        conn = "mongodb://root:pass@192.168.1.100:27017/admin"
        with pytest.raises(ValueError, match="private/internal"):
            validate_connection_string(conn)

    def test_rejects_metadata_ip(self):
        conn = "mongodb://root:pass@169.254.169.254:27017/admin"
        with pytest.raises(ValueError, match="private/internal"):
            validate_connection_string(conn)

    def test_rejects_arbitrary_host(self):
        conn = "mongodb://root:pass@attacker.com:27017/admin"
        with pytest.raises(ValueError, match="not allowed"):
            validate_connection_string(conn)

    def test_rejects_no_hostname(self):
        conn = "not_a_valid_uri"
        with pytest.raises(ValueError, match="no hostname"):
            validate_connection_string(conn)

    def test_allows_env_configured_host(self, monkeypatch):
        monkeypatch.setenv("MONGODB_CONNECTION_STRING", "mongodb://u:p@myhost.example.com:27017/db")
        conn = "mongodb://root:pass@myhost.example.com:27017/admin"
        validate_connection_string(conn)

    def test_allows_env_host_param(self, monkeypatch):
        monkeypatch.delenv("MONGODB_CONNECTION_STRING", raising=False)
        monkeypatch.setenv("MONGODB_HOST", "custom.mongo.internal.corp")
        conn = "mongodb://root:pass@custom.mongo.internal.corp:27017/admin"
        validate_connection_string(conn)

    def test_allows_custom_suffix_via_env(self, monkeypatch):
        monkeypatch.setenv("MONGODB_ALLOWED_HOST_SUFFIXES", ".mongo.mycompany.com")
        conn = "mongodb://root:pass@db1.mongo.mycompany.com:27017/admin"
        validate_connection_string(conn)
