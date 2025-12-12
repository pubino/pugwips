# Shared Task Notes

## Current Status: Live on GitHub

Repository: https://github.com/pubino/pugwips

The VPN Gateway IP Resolver is now live with automated updates every 6 hours via GitHub Actions.

## What's Working
- GitHub Actions workflows: both Test and Resolve workflows passing
- Scheduled IP resolution every 6 hours (commits directly to `main`)
- Tests run in CI with pytest
- Output files in `output/` directory are kept up-to-date automatically

## Available Outputs (always current)
- `output/resolved_gateways.json` - Full JSON with metadata
- `output/ip_list.txt` - Plain IP list (one per line)
- `output/azure_ip_group.json` - Azure IP Group format
- `output/ip_group.bicep` - Bicep template
- `output/ip_group.tf` - Terraform template

## Next Steps (Optional Enhancements)

### 1. Update Azure Function config (if deploying API)
In `azure-function/resolve_gateway_ips/__init__.py`, change:
```python
DEFAULT_OWNER = "pubino"  # Already set to correct value
```

### 2. Deploy Azure Function (optional)
For on-demand HTTP API access:
```bash
cd /Users/bino/Downloads/pugwips
export GITHUB_OWNER="pubino"
./infra/deploy.sh
```

### 3. Set up Codecov (optional)
To enable coverage reporting, add a `CODECOV_TOKEN` secret to the repo.

### 4. Create Azure IP Group from outputs
Use the Bicep or Terraform templates in `output/` to create an IP Group in Azure:
```bash
# Using Azure CLI with Bicep
az deployment group create \
  --resource-group YOUR_RG \
  --template-file output/ip_group.bicep
```

## Project Structure
```
├── gateways.txt              # Input: VPN gateway hostnames
├── resolve_gateways.py       # Main resolver script
├── output/                   # Auto-updated output files
├── .github/workflows/        # GitHub Actions (test + resolve)
├── azure-function/           # Azure Function code (optional)
├── infra/                    # Bicep + deploy/teardown scripts
├── tests/                    # pytest unit tests
└── README.md                 # Full documentation
```
