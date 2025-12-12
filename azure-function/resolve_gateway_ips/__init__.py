"""
Azure Function to resolve VPN gateway hostnames to IPs on demand.

This function fetches the latest gateways.txt from GitHub and resolves all hostnames.
"""

import json
import logging
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.request import urlopen
from urllib.error import URLError

import azure.functions as func


# Configuration - update this to your repository
GITHUB_RAW_URL = "https://raw.githubusercontent.com/{owner}/{repo}/main/gateways.txt"
DEFAULT_OWNER = "YOUR_GITHUB_USERNAME"
DEFAULT_REPO = "pugwips"


def parse_gateways(content: str) -> list[str]:
    """Parse gateway hostnames from file content."""
    hostnames = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        hostnames.append(line)
    return hostnames


def resolve_hostname(hostname: str) -> dict:
    """Resolve a single hostname to IP addresses."""
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_INET)
        ips = sorted(set(result[4][0] for result in results))
        return {"hostname": hostname, "ips": ips, "error": None}
    except socket.gaierror as e:
        return {"hostname": hostname, "ips": [], "error": str(e)}
    except Exception as e:
        return {"hostname": hostname, "ips": [], "error": str(e)}


def resolve_all(hostnames: list[str], max_workers: int = 20) -> list[dict]:
    """Resolve all hostnames concurrently."""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_hostname = {
            executor.submit(resolve_hostname, hostname): hostname
            for hostname in hostnames
        }
        for future in as_completed(future_to_hostname):
            results.append(future.result())
    return sorted(results, key=lambda r: r["hostname"])


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("VPN Gateway IP resolution function triggered")

    # Get optional parameters
    owner = req.params.get("owner", DEFAULT_OWNER)
    repo = req.params.get("repo", DEFAULT_REPO)
    output_format = req.params.get("format", "json")

    # Allow POST body to override
    try:
        req_body = req.get_json()
        owner = req_body.get("owner", owner)
        repo = req_body.get("repo", repo)
        output_format = req_body.get("format", output_format)
    except ValueError:
        pass

    # Fetch gateways.txt from GitHub
    url = GITHUB_RAW_URL.format(owner=owner, repo=repo)

    try:
        with urlopen(url, timeout=30) as response:
            content = response.read().decode("utf-8")
    except URLError as e:
        return func.HttpResponse(
            json.dumps({"error": f"Failed to fetch gateways.txt: {str(e)}"}),
            status_code=500,
            mimetype="application/json",
        )

    # Parse and resolve
    hostnames = parse_gateways(content)
    results = resolve_all(hostnames)

    # Calculate stats
    all_ips = set()
    for r in results:
        all_ips.update(r["ips"])

    response_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_gateways": len(results),
        "successful": sum(1 for r in results if r["ips"]),
        "failed": sum(1 for r in results if r["error"]),
        "unique_ips": len(all_ips),
    }

    if output_format == "ips":
        # Return just the IP list
        return func.HttpResponse(
            "\n".join(sorted(all_ips)),
            mimetype="text/plain",
        )
    elif output_format == "azure":
        # Return Azure IP Group format
        response_data = {
            "name": "vpn-gateways-ip-group",
            "properties": {"ipAddresses": sorted(all_ips)},
        }
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            mimetype="application/json",
        )
    else:
        # Full JSON response
        response_data["gateways"] = results
        response_data["all_ips"] = sorted(all_ips)
        return func.HttpResponse(
            json.dumps(response_data, indent=2),
            mimetype="application/json",
        )
