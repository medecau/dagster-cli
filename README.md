# Dagster CLI (dgc)

A command-line interface for Dagster+, inspired by GitHub's `gh` CLI.

## Installation

```bash
# Install with uv (recommended - adds 'dgc' to PATH)
uv tool install dagster-cli

# Or run without installation (temporary use)
uvx --from dagster-cli dgc auth login

# Or install with pip
pip install dagster-cli

# Or from source
git clone https://github.com/yourusername/dagster-cli.git
cd dagster-cli
uv pip install -e .
```

## Quick Start

```bash
# 1. Authenticate with your Dagster+ deployment
dgc auth login
# Enter your Dagster+ URL: your-org.dagster.cloud/prod
# Enter your User Token: (from Organization Settings → Tokens)

# 2. Start using dgc
dgc job list                    # List all jobs
dgc run list --status FAILURE   # View failed runs
dgc asset health                # Check asset health
```

## Features

- **Secure Authentication** - Store credentials safely with profile support
- **Job Management** - List, view, and run Dagster jobs from the terminal
- **Run Monitoring** - Track run status, view logs, and analyze failures
- **Asset Management** - List, materialize, and monitor asset health
- **Repository Operations** - List and reload code locations
- **Profile Support** - Manage multiple Dagster+ deployments
- **MCP Integration** - AI assistant integration for monitoring and debugging

## Common Commands

### Authentication & Profiles
```bash
dgc auth login                  # Initial setup
dgc auth status                 # View current profile
dgc auth switch production      # Change profile
```

### Jobs & Runs
```bash
dgc job list                    # List all jobs
dgc job run my_job              # Submit a job
dgc job run my_job --config '{...}'  # Run with config

dgc run list                    # Recent runs
dgc run list --status FAILURE   # Failed runs only
dgc run view abc123             # Run details
dgc run logs abc123             # View run logs (events + auto stderr on errors)
dgc run logs abc123 --stdout    # View stdout logs
dgc run logs abc123 --stderr    # View stderr logs
```

### Assets
```bash
dgc asset list                  # All assets
dgc asset health                # Check health status
dgc asset materialize my_asset  # Trigger materialization
```

### Repository Management
```bash
dgc repo list                   # List locations
dgc repo reload my_location     # Reload code
```

## Configuration

### Multiple Profiles
```bash
dgc auth login --profile staging    # Create new profile
dgc job list --profile production   # Use specific profile
dgc auth switch staging             # Set default profile
```

### Environment Variables
- `DAGSTER_CLOUD_TOKEN` - User token
- `DAGSTER_CLOUD_URL` - Deployment URL
- `DGC_PROFILE` - Default profile

Credentials stored in `~/.config/dagster-cli/config.json` (permissions: 600)

## Output Options

Use `--json` flag for scripting:
```bash
# Filter jobs by name
dgc job list --json | jq '.[] | select(.name | contains("etl"))'

# Submit job and get run ID
RUN_ID=$(dgc job run my_etl_job --json | jq -r '.run_id')
```

## AI Assistant Integration (MCP)

Enable AI assistants to monitor and debug your Dagster+ deployment:

```bash
# Start MCP server for local AI assistants
dgc mcp start

# For Claude Desktop, add to config:
{
  "servers": {
    "dagster-cli": {
      "command": "dgc",
      "args": ["mcp", "start"]
    }
  }
}
```

Common AI use cases:
- "Check which assets are failing and need attention"
- "Why did the daily_revenue job fail yesterday?"
- "Materialize all stale marketing assets"

## Development

```bash
# Run tests
uv run pytest

# Format and lint
make fix

# Build package
uv build
```

For more details, see the [full documentation](https://github.com/yourusername/dagster-cli/wiki).