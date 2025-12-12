"""Tests for resolve_gateways.py"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from resolve_gateways import (
    parse_gateways_file,
    resolve_hostname,
    resolve_all_gateways,
    generate_json_output,
    generate_ip_list,
    generate_azure_ip_group_json,
    generate_bicep_output,
    generate_terraform_output,
    ResolvedGateway,
)


class TestParseGatewaysFile:
    def test_parse_valid_file(self, tmp_path):
        """Test parsing a valid gateways file."""
        content = """# Comment line
host1.example.com
host2.example.com

# Another comment
host3.example.com
"""
        file_path = tmp_path / "gateways.txt"
        file_path.write_text(content)

        result = parse_gateways_file(file_path)

        assert result == [
            "host1.example.com",
            "host2.example.com",
            "host3.example.com",
        ]

    def test_parse_empty_file(self, tmp_path):
        """Test parsing an empty file."""
        file_path = tmp_path / "empty.txt"
        file_path.write_text("")

        result = parse_gateways_file(file_path)

        assert result == []

    def test_parse_comments_only(self, tmp_path):
        """Test parsing a file with only comments."""
        content = """# Comment 1
# Comment 2
"""
        file_path = tmp_path / "comments.txt"
        file_path.write_text(content)

        result = parse_gateways_file(file_path)

        assert result == []


class TestResolveHostname:
    @patch("resolve_gateways.socket.getaddrinfo")
    def test_resolve_success(self, mock_getaddrinfo):
        """Test successful hostname resolution."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("1.2.3.4", 0)),
            (2, 1, 6, "", ("5.6.7.8", 0)),
        ]

        result = resolve_hostname("example.com")

        assert result.hostname == "example.com"
        assert result.ips == ["1.2.3.4", "5.6.7.8"]
        assert result.error is None

    @patch("resolve_gateways.socket.getaddrinfo")
    def test_resolve_failure(self, mock_getaddrinfo):
        """Test failed hostname resolution."""
        import socket
        mock_getaddrinfo.side_effect = socket.gaierror(8, "Name does not resolve")

        result = resolve_hostname("nonexistent.invalid")

        assert result.hostname == "nonexistent.invalid"
        assert result.ips == []
        assert result.error is not None

    @patch("resolve_gateways.socket.getaddrinfo")
    def test_resolve_deduplicates_ips(self, mock_getaddrinfo):
        """Test that duplicate IPs are deduplicated."""
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("1.2.3.4", 0)),
            (2, 1, 6, "", ("1.2.3.4", 0)),
            (2, 1, 6, "", ("5.6.7.8", 0)),
        ]

        result = resolve_hostname("example.com")

        assert result.ips == ["1.2.3.4", "5.6.7.8"]


class TestResolveAllGateways:
    @patch("resolve_gateways.resolve_hostname")
    def test_resolve_all(self, mock_resolve):
        """Test resolving multiple hostnames."""
        mock_resolve.side_effect = [
            ResolvedGateway("host1.com", ["1.1.1.1"]),
            ResolvedGateway("host2.com", ["2.2.2.2"]),
        ]

        result = resolve_all_gateways(["host1.com", "host2.com"], max_workers=2)

        assert len(result) == 2
        # Results should be sorted by hostname
        assert result[0].hostname == "host1.com"
        assert result[1].hostname == "host2.com"


class TestGenerateJsonOutput:
    def test_generate_json_output(self):
        """Test JSON output generation."""
        results = [
            ResolvedGateway("host1.com", ["1.1.1.1"]),
            ResolvedGateway("host2.com", [], error="Resolution failed"),
        ]

        output = generate_json_output(results)

        assert output["total_gateways"] == 2
        assert output["successful_resolutions"] == 1
        assert output["failed_resolutions"] == 1
        assert len(output["gateways"]) == 2
        assert "generated_at" in output


class TestGenerateIpList:
    def test_generate_ip_list(self):
        """Test IP list generation."""
        results = [
            ResolvedGateway("host1.com", ["1.1.1.1", "2.2.2.2"]),
            ResolvedGateway("host2.com", ["3.3.3.3", "1.1.1.1"]),  # Duplicate
        ]

        ip_list = generate_ip_list(results)

        assert ip_list == ["1.1.1.1", "2.2.2.2", "3.3.3.3"]

    def test_generate_ip_list_empty(self):
        """Test IP list generation with no results."""
        ip_list = generate_ip_list([])
        assert ip_list == []


class TestGenerateAzureIpGroupJson:
    def test_generate_azure_format(self):
        """Test Azure IP Group JSON generation."""
        results = [
            ResolvedGateway("host1.com", ["1.1.1.1"]),
            ResolvedGateway("host2.com", ["2.2.2.2"]),
        ]

        output = generate_azure_ip_group_json(results)

        assert output["name"] == "vpn-gateways-ip-group"
        assert "properties" in output
        assert output["properties"]["ipAddresses"] == ["1.1.1.1", "2.2.2.2"]


class TestGenerateBicepOutput:
    def test_generate_bicep(self):
        """Test Bicep file generation."""
        results = [
            ResolvedGateway("host1.com", ["1.1.1.1"]),
        ]

        output = generate_bicep_output(results)

        assert "Microsoft.Network/ipGroups" in output
        assert "'1.1.1.1'" in output
        assert "param location string" in output


class TestGenerateTerraformOutput:
    def test_generate_terraform(self):
        """Test Terraform file generation."""
        results = [
            ResolvedGateway("host1.com", ["1.1.1.1"]),
        ]

        output = generate_terraform_output(results)

        assert "azurerm_ip_group" in output
        assert '"1.1.1.1"' in output
        assert "variable" in output


class TestIntegration:
    """Integration tests that perform actual DNS lookups."""

    @pytest.mark.integration
    def test_resolve_real_hostname(self):
        """Test resolving a real hostname (google.com)."""
        result = resolve_hostname("google.com")

        assert result.hostname == "google.com"
        assert len(result.ips) > 0
        assert result.error is None

    @pytest.mark.integration
    def test_resolve_nonexistent_hostname(self):
        """Test resolving a nonexistent hostname."""
        result = resolve_hostname("this-hostname-definitely-does-not-exist.invalid")

        assert result.hostname == "this-hostname-definitely-does-not-exist.invalid"
        assert result.ips == []
        assert result.error is not None
