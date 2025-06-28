# Dagster CLI (dgc)

A command-line interface for Dagster+, inspired by GitHub's `gh` CLI.

## Installation

```bash
# Install with uv (recommended - adds 'dgc' to PATH)
uv tool install dagster-cli

# Or install with pip
pip install dagster-cli
```

## Quick Start

```bash
# Authenticate with your Dagster+ deployment
dgc auth login

# Check health status of all assets (find problems)
dgc asset health

# View details about a specific asset
dgc asset view analytics/daily_revenue

# View logs for a failed run (see stack traces)
dgc run logs abc123 --stderr

# List recent runs to find failures
dgc run list --limit 10
```

**Note:** All commands support `--help` for detailed options and `--tldr` for quick examples.

## MCP Server for AI Assistants

Run the MCP server without installation using uvx:

```bash
# Start MCP server for Claude Code integration
uvx --from dagster-cli dgc mcp start
```

Configure Claude Code by adding to your MCP settings:

```json
{
  "mcpServers": {
    "dagster-cli": {
      "command": "uvx",
      "args": ["--from", "dagster-cli", "dgc", "mcp", "start"]
    }
  }
}
```

This enables AI assistants to:
- Check asset health and identify failures
- Investigate failed runs and view error logs
- Monitor job execution and debug issues
- Access stderr/stdout logs for troubleshooting

## Working with Branch Deployments

```bash
# List all deployments including branches
dgc deployment list

# Get filtered logs from a branch deployment (e.g., for PR review)
dgc run list --deployment feat-new-feature --status FAILURE --limit 5
dgc run logs abc123 --deployment feat-new-feature --stderr

# Filter runs by job name on a specific deployment
dgc run list --deployment staging --job daily_etl --limit 10
```

## Features

- **Secure Authentication** - Store credentials safely with profile support
- **Job Management** - List, view, and run Dagster jobs from the terminal
- **Run Monitoring** - Track run status, view logs, and analyze failures
- **Asset Management** - List, materialize, and monitor asset health
- **Repository Operations** - List and reload code locations
- **Profile Support** - Manage multiple Dagster+ deployments
- **Branch Deployment Support** - Access branch deployments for testing and debugging
- **Deployment Discovery** - List and test available deployments
- **MCP Integration** - AI assistant integration for monitoring and debugging

## Configuration

### Authentication
```bash
dgc auth login                  # Set up credentials
dgc auth status                 # View current profile
dgc auth switch staging         # Switch between profiles
```

### Multiple Profiles
```bash
dgc auth login --profile staging    # Create new profile
dgc job list --profile production   # Use specific profile
```

### Environment Variables
- `DAGSTER_CLOUD_TOKEN` - User token
- `DAGSTER_CLOUD_URL` - Deployment URL  
- `DGC_PROFILE` - Default profile
- `DAGSTER_CLOUD_DEPLOYMENT` - Default deployment

Credentials stored in `~/.config/dagster-cli/config.json`


## Development

```bash
# Run tests
uv run pytest

# Format and lint
make fix

# Build package
uv build
```

