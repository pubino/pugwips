#!/usr/bin/env python3
"""
VPN Gateway DNS Resolver

Resolves VPN gateway hostnames to IP addresses and outputs in multiple formats
suitable for Azure IP Groups and other networking configurations.
"""

import argparse
import json
import socket
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ResolvedGateway:
    hostname: str
    ips: list[str]
    error: str | None = None


def parse_gateways_file(file_path: Path) -> list[str]:
    """Parse the gateways file and return list of hostnames."""
    hostnames = []
    with open(file_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            hostnames.append(line)
    return hostnames


def resolve_hostname(hostname: str) -> ResolvedGateway:
    """Resolve a single hostname to IP addresses."""
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_INET)
        ips = sorted(set(result[4][0] for result in results))
        return ResolvedGateway(hostname=hostname, ips=ips)
    except socket.gaierror as e:
        return ResolvedGateway(hostname=hostname, ips=[], error=str(e))
    except Exception as e:
        return ResolvedGateway(hostname=hostname, ips=[], error=str(e))


def resolve_all_gateways(
    hostnames: list[str], max_workers: int = 20
) -> list[ResolvedGateway]:
    """Resolve all hostnames concurrently."""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_hostname = {
            executor.submit(resolve_hostname, hostname): hostname
            for hostname in hostnames
        }
        for future in as_completed(future_to_hostname):
            results.append(future.result())
    # Sort by hostname for consistent output
    return sorted(results, key=lambda r: r.hostname)


def generate_json_output(results: list[ResolvedGateway]) -> dict:
    """Generate JSON output with full details."""
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_gateways": len(results),
        "successful_resolutions": sum(1 for r in results if r.ips),
        "failed_resolutions": sum(1 for r in results if r.error),
        "gateways": [
            {"hostname": r.hostname, "ips": r.ips, "error": r.error} for r in results
        ],
    }


def generate_ip_list(results: list[ResolvedGateway]) -> list[str]:
    """Generate a flat list of unique IPs."""
    all_ips = set()
    for result in results:
        all_ips.update(result.ips)
    return sorted(all_ips)


def generate_azure_ip_group_json(results: list[ResolvedGateway]) -> dict:
    """Generate Azure IP Group compatible JSON."""
    return {
        "name": "vpn-gateways-ip-group",
        "location": "[resourceGroup().location]",
        "properties": {"ipAddresses": generate_ip_list(results)},
    }


def generate_bicep_output(results: list[ResolvedGateway]) -> str:
    """Generate Azure Bicep file for IP Group."""
    ips = generate_ip_list(results)
    ip_array = "\n".join(f"    '{ip}'" for ip in ips)

    return f"""// Auto-generated VPN Gateway IP Group
// Generated at: {datetime.now(timezone.utc).isoformat()}
// Total IPs: {len(ips)}

param location string = resourceGroup().location
param ipGroupName string = 'vpn-gateways-ip-group'

resource ipGroup 'Microsoft.Network/ipGroups@2023-05-01' = {{
  name: ipGroupName
  location: location
  properties: {{
    ipAddresses: [
{ip_array}
    ]
  }}
}}

output ipGroupId string = ipGroup.id
"""


def generate_terraform_output(results: list[ResolvedGateway]) -> str:
    """Generate Terraform file for Azure IP Group."""
    ips = generate_ip_list(results)
    ip_list = ",\n    ".join(f'"{ip}"' for ip in ips)

    return f"""# Auto-generated VPN Gateway IP Group
# Generated at: {datetime.now(timezone.utc).isoformat()}
# Total IPs: {len(ips)}

variable "resource_group_name" {{
  description = "The name of the resource group"
  type        = string
}}

variable "location" {{
  description = "The Azure region"
  type        = string
}}

resource "azurerm_ip_group" "vpn_gateways" {{
  name                = "vpn-gateways-ip-group"
  location            = var.location
  resource_group_name = var.resource_group_name

  cidrs = [
    {ip_list}
  ]
}}

output "ip_group_id" {{
  value = azurerm_ip_group.vpn_gateways.id
}}
"""


def main():
    parser = argparse.ArgumentParser(
        description="Resolve VPN gateway hostnames to IP addresses"
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=Path("gateways.txt"),
        help="Input file with gateway hostnames (default: gateways.txt)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Output directory for generated files (default: output)",
    )
    parser.add_argument(
        "--format",
        choices=["all", "json", "ips", "azure", "bicep", "terraform"],
        default="all",
        help="Output format (default: all)",
    )
    parser.add_argument(
        "--workers", type=int, default=20, help="Max concurrent DNS lookups (default: 20)"
    )

    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: Input file '{args.input}' not found", file=sys.stderr)
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Parsing gateways from {args.input}...")
    hostnames = parse_gateways_file(args.input)
    print(f"Found {len(hostnames)} gateways to resolve")

    print(f"Resolving DNS with {args.workers} workers...")
    results = resolve_all_gateways(hostnames, args.workers)

    successful = sum(1 for r in results if r.ips)
    failed = sum(1 for r in results if r.error)
    print(f"Resolution complete: {successful} successful, {failed} failed")

    if failed > 0:
        print("\nFailed resolutions:")
        for r in results:
            if r.error:
                print(f"  - {r.hostname}: {r.error}")

    formats_to_generate = (
        ["json", "ips", "azure", "bicep", "terraform"]
        if args.format == "all"
        else [args.format]
    )

    for fmt in formats_to_generate:
        if fmt == "json":
            output_file = args.output_dir / "resolved_gateways.json"
            with open(output_file, "w") as f:
                json.dump(generate_json_output(results), f, indent=2)
            print(f"Written: {output_file}")

        elif fmt == "ips":
            output_file = args.output_dir / "ip_list.txt"
            with open(output_file, "w") as f:
                f.write("\n".join(generate_ip_list(results)))
            print(f"Written: {output_file}")

        elif fmt == "azure":
            output_file = args.output_dir / "azure_ip_group.json"
            with open(output_file, "w") as f:
                json.dump(generate_azure_ip_group_json(results), f, indent=2)
            print(f"Written: {output_file}")

        elif fmt == "bicep":
            output_file = args.output_dir / "ip_group.bicep"
            with open(output_file, "w") as f:
                f.write(generate_bicep_output(results))
            print(f"Written: {output_file}")

        elif fmt == "terraform":
            output_file = args.output_dir / "ip_group.tf"
            with open(output_file, "w") as f:
                f.write(generate_terraform_output(results))
            print(f"Written: {output_file}")

    print("\nDone!")


if __name__ == "__main__":
    main()
