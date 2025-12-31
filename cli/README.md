# Hyperclast CLI

A command-line interface for interacting with Hyperclast. Pipe command output directly to pages, manage projects, and more.

## Installation

### From Binary (Recommended)

Download the latest release for your platform from the [releases page](https://github.com/hyperclast/workspace/releases).

```bash
# macOS (Apple Silicon)
curl -L https://github.com/hyperclast/workspace/releases/latest/download/hyperclast-darwin-arm64 -o hyperclast
chmod +x hyperclast
sudo mv hyperclast /usr/local/bin/

# macOS (Intel)
curl -L https://github.com/hyperclast/workspace/releases/latest/download/hyperclast-darwin-amd64 -o hyperclast
chmod +x hyperclast
sudo mv hyperclast /usr/local/bin/

# Linux (x86_64)
curl -L https://github.com/hyperclast/workspace/releases/latest/download/hyperclast-linux-amd64 -o hyperclast
chmod +x hyperclast
sudo mv hyperclast /usr/local/bin/
```

**macOS Gatekeeper:** If you see "cannot be opened because the developer cannot be verified", run:

```bash
xattr -d com.apple.quarantine ./hyperclast
```

### From Source

```bash
cd cli
go build -o hyperclast .
```

## Quick Start

```bash
# 1. Authenticate with your API token
hyperclast auth login

# 2. List your projects
hyperclast project list

# 3. Set a default project
hyperclast project use proj_abc123

# 4. Pipe command output to a new page
make build 2>&1 | hyperclast page new --title "Build Log"
```

## Commands

### Authentication

```bash
hyperclast auth login     # Enter and store API token
hyperclast auth logout    # Remove stored credentials
hyperclast auth status    # Check authentication status
```

**Getting your API token:**

1. Log into Hyperclast web app
2. Go to Settings → API
3. Copy your API token

### Organizations

```bash
hyperclast org list       # List organizations you belong to
hyperclast org current    # Show current default organization
hyperclast org use <id>   # Set default organization
```

### Projects

```bash
hyperclast project list [--org <id>]   # List projects (uses default org if not specified)
hyperclast project current             # Show default project
hyperclast project use <id>            # Set default project
```

### Pages

```bash
# Create a new page from stdin
hyperclast page new --project <id> --title "Title"
hyperclast page new -p <id> -t "Title"

# Pipe command output
cat build.log | hyperclast page new -p proj_abc -t "Build Output"
./run-tests.sh 2>&1 | hyperclast page new -p proj_abc -t "Test Results"

# With default project configured
make build 2>&1 | hyperclast page new -t "Build Log"

# Title defaults to timestamp if not provided
echo "Quick note" | hyperclast page new -p proj_abc
# Creates page titled "Dec 30, 2025 at 2:45 PM"

# From file instead of stdin
hyperclast page new -p proj_abc -t "Config" --file ./config.txt

# List pages
hyperclast page list [--project <id>]

# Get page content (outputs to stdout)
hyperclast page get <page-id>
hyperclast page get <page-id> > backup.txt
```

## Global Flags

```bash
--config <path>     # Custom config file location (default: ~/.config/hyperclast/config.yaml)
--api-url <url>     # API URL (default: https://hyperclast.com/api)
--output json       # Output in JSON format (for scripting)
--quiet             # Suppress info messages, only output result
--verbose           # Show debug output
```

## Configuration

Configuration is stored in `~/.config/hyperclast/config.yaml`:

```yaml
api_url: https://hyperclast.com/api
token: your-api-token-here
defaults:
  org_id: org_abc123
  project_id: proj_xyz789
```

## Examples

### CI/CD Integration

```bash
# In your CI pipeline, save build logs to Hyperclast
npm run build 2>&1 | hyperclast page new \
  --project proj_builds \
  --title "Build #${CI_BUILD_NUMBER} - $(date +%Y-%m-%d)"
```

### Daily Notes

```bash
# Create a daily note
echo "## $(date +%Y-%m-%d)\n\n- Task 1\n- Task 2" | hyperclast page new -t "Daily Note"
```

### Backup Scripts

```bash
# Save server status to a page
(uptime; free -h; df -h) | hyperclast page new -t "Server Status $(date +%H:%M)"
```

### Capture Command Output

```bash
# Save any command output
git log --oneline -20 | hyperclast page new -t "Recent Commits"
docker ps -a | hyperclast page new -t "Container Status"
```

## Error Handling

The CLI provides helpful error messages:

```bash
# No project specified and no default set
$ echo "test" | hyperclast page new -t "Test"
Error: No project specified.
  Use --project <id> or set a default: hyperclast project use <id>
  Run 'hyperclast project list' to see available projects.

# No content provided
$ hyperclast page new -p proj_abc -t "Empty"
Error: No content provided. Pipe content or use --file <path>

# Not authenticated
$ hyperclast project list
Error: Not authenticated. Run 'hyperclast auth login' first.
```

## Development

### Building

```bash
cd cli
go build -o hyperclast .
```

### Cross-compilation

```bash
# Build for all platforms
make build-all

# Or manually:
GOOS=darwin GOARCH=arm64 go build -o hyperclast-darwin-arm64 .
GOOS=darwin GOARCH=amd64 go build -o hyperclast-darwin-amd64 .
GOOS=linux GOARCH=amd64 go build -o hyperclast-linux-amd64 .
GOOS=windows GOARCH=amd64 go build -o hyperclast-windows-amd64.exe .
```

### Running Tests

```bash
go test ./...
```

## License

See the main project LICENSE file.
