# Dagster CLI (dgc)

A command-line interface for Dagster+, inspired by GitHub's `gh` CLI.

## Features

- 🔐 **Secure Authentication** - Store credentials safely with profile support
- 📋 **Job Management** - List, view, and run Dagster jobs
- 🏃 **Run Monitoring** - Track run status and history
- 💎 **Asset Management** - List, view, materialize, and monitor asset health
- 🏗️ **Repository Operations** - List and reload code locations
- 🎨 **Rich Terminal UI** - Beautiful tables and formatted output
- 🔧 **Profile Support** - Manage multiple Dagster+ deployments
- 🤖 **MCP Integration** - Expose Dagster+ functionality to AI assistants via Model Context Protocol

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/dagster-cli.git
cd dagster-cli

# Install with uv (recommended)
uv sync
uv pip install -e .

# Or install with pip
pip install -e .
```

### Verify Installation

```bash
dgc --version
```

## Quick Start

### 1. Authenticate with Dagster+

```bash
dgc auth login
```

You'll be prompted for:
- Your Dagster+ URL (e.g., `your-org.dagster.cloud/prod`)
- Your User Token (from Dagster+ → Organization Settings → Tokens)

### 2. Explore Available Commands

```bash
# List all jobs
dgc job list

# View recent runs
dgc run list

# Show repository information
dgc repo list
```

## Command Reference

### Authentication

```bash
# Login to Dagster+
dgc auth login

# Check authentication status
dgc auth status

# Switch between profiles
dgc auth switch production

# Logout
dgc auth logout
```

### Jobs

```bash
# List all jobs
dgc job list

# List jobs in specific location
dgc job list --location data_etl

# View job details
dgc job view my_job_name

# Run a job
dgc job run my_job_name

# Run with configuration
dgc job run my_job_name --config '{"ops": {"my_op": {"config": {"param": "value"}}}}'
```

### Runs

```bash
# List recent runs
dgc run list

# List failed runs
dgc run list --status FAILURE

# View run details
dgc run view 8a7c9d1e

# View run logs (coming soon)
dgc run logs 8a7c9d1e
```

### Assets

```bash
# List all assets
dgc asset list

# List assets with prefix
dgc asset list --prefix data/

# View asset details
dgc asset view my_dataset

# Check asset health (shows unhealthy only)
dgc asset health

# Show all assets with health status
dgc asset health --all

# Set custom staleness threshold
dgc asset health --stale-hours 48

# Materialize an asset
dgc asset materialize my_dataset
```

### Repositories

```bash
# List all repositories and locations
dgc repo list

# Reload a repository location
dgc repo reload my_location
```

### Configuration

```bash
# Show current configuration
dgc config --list

# Check overall status
dgc status
```

## Profiles

Manage multiple Dagster+ deployments with profiles:

```bash
# Create a new profile during login
dgc auth login --profile staging

# Use a specific profile for a command
dgc job list --profile staging

# Set default profile
dgc auth switch staging

# List all profiles
dgc auth status
```

## Environment Variables

The CLI respects these environment variables:

- `DAGSTER_CLOUD_TOKEN` - Your User Token
- `DAGSTER_CLOUD_URL` - Dagster+ deployment URL
- `DAGSTER_CLOUD_LOCATION` - Default repository location
- `DAGSTER_CLOUD_REPOSITORY` - Default repository name
- `DGC_PROFILE` - Default profile to use

## Configuration Files

Credentials are stored in `~/.config/dagster-cli/config.json` with restricted permissions (600).

Example structure:
```json
{
  "version": "1.0",
  "profiles": {
    "default": {
      "url": "myorg.dagster.cloud/prod",
      "token": "user:...",
      "location": "data_etl",
      "repository": "__repository__"
    }
  },
  "current_profile": "default"
}
```

## Output Formats

### Tables (default)
```bash
dgc job list
```

### JSON (for scripting)
```bash
dgc job list --json | jq '.[] | select(.name | contains("etl"))'
```

## Examples

### Submit a job and monitor its progress
```bash
# Submit job
RUN_ID=$(dgc job run my_etl_job --json | jq -r '.run_id')

# Check status
dgc run view $RUN_ID
```

### List all failed runs from today
```bash
dgc run list --status FAILURE --limit 50 | grep "$(date +%Y-%m-%d)"
```

### Reload all repository locations
```bash
dgc repo list --json | jq -r '.[].location' | xargs -I {} dgc repo reload {}
```

## MCP (Model Context Protocol) Integration

The Dagster CLI includes an MCP server that exposes Dagster+ functionality to AI assistants like Claude, Cursor, and other MCP-compatible tools. This is particularly useful for monitoring asset health and debugging failed runs.

### Starting the MCP Server

```bash
# Start in stdio mode (default - for local AI assistants)
dgc mcp start

# Start in HTTP mode (for remote access)
dgc mcp start --http
```

### Available MCP Tools

The MCP server exposes the following tools:

- **list_jobs** - List available Dagster jobs
- **run_job** - Submit a job for execution
- **get_run_status** - Get status and details of a specific run
- **list_runs** - Get recent run history with filtering
- **list_assets** - List all assets with optional filtering
- **materialize_asset** - Trigger asset materialization
- **reload_repository** - Reload a repository location

### Common Use Cases

#### Asset Health Monitoring
AI assistants can check asset health and identify stale or failed assets:
```
"Check the health of all analytics assets and tell me which ones need attention"
```

#### Debugging Failed Assets
When assets fail, AI assistants can investigate by:
1. Checking asset status and last materialization time
2. Finding the failed run ID
3. Getting run details to understand the failure
```
"The daily_revenue asset is failing. Can you check what's wrong?"
```

### Integration with AI Tools

#### Claude Desktop
Add to your Claude Desktop configuration:
```json
{
  "servers": {
    "dagster-cli": {
      "command": "dgc",
      "args": ["mcp", "start"]
    }
  }
}
```

#### Other MCP Clients
The HTTP mode allows integration with any MCP-compatible client:
```bash
dgc mcp start --http
# Server runs on http://localhost:8000
# MCP endpoint: http://localhost:8000/mcp
```

## Security

- Credentials are stored in your home directory with restricted permissions
- Tokens are never displayed in logs or error messages
- Use environment variables for CI/CD environments
- Profile support allows separation of dev/staging/prod credentials

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

## License

MIT License - see LICENSE file for details