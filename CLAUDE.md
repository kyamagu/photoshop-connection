# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Install dependencies
```bash
# Install main dependencies only
uv sync

# Install with dev dependencies
uv sync --group dev

# Install with all groups and extras
uv sync --all-groups --all-extras
```

### Run tests
```bash
uv run pytest
```

### Run tests with coverage
```bash
uv run pytest --cov-report term-missing --cov=photoshop
```

### Run a single test file
```bash
uv run pytest tests/<test_file.py>
```

### Build package
```bash
uv build
```

### Linting
```bash
uv run ruff check src/ tests/
```

### Fix linting issues
```bash
uv run ruff check --fix src/ tests/
```

### Create virtual environment (if needed)
```bash
uv venv
```

### Activate virtual environment
```bash
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate  # On Windows
```

## Architecture

This is a Python package for remotely executing ExtendScript in Adobe Photoshop via socket connection.

### Core Components

- **PhotoshopConnection** (src/photoshop/photoshop_connection.py): Main class that manages socket connection to Photoshop. Handles authentication, command execution, and maintains a thread-based dispatcher for async communication.

- **Protocol** (src/photoshop/protocol.py): Implements the communication protocol with Photoshop, including encryption/decryption of messages and message formatting.

- **API Module** (src/photoshop/api.py): Contains the Event and Kevlar classes with high-level methods for Photoshop operations like getting document info, thumbnails, and managing event subscriptions.

- **JavaScript Templates** (src/photoshop/api/*.js.j2): Jinja2 templates for ExtendScript commands that are rendered and sent to Photoshop.

### Communication Flow

1. Client establishes encrypted socket connection to Photoshop (default port 49494)
2. Commands are sent as ExtendScript JavaScript code
3. Photoshop executes the script and returns results
4. Results are encrypted and sent back through the socket
5. A dispatcher thread handles async responses and routes them to transactions

### Key Design Patterns

- **Context Manager**: PhotoshopConnection uses context manager pattern for safe connection handling
- **Thread-based Dispatcher**: Async message handling via dedicated dispatcher thread
- **Transaction System**: Each command execution is tracked as a transaction with unique ID
- **Template-based Commands**: Complex ExtendScript commands are built from Jinja2 templates

## Testing

Tests require a running Photoshop instance with remote connections enabled. Set the PHOTOSHOP_PASSWORD environment variable before running tests.

## Dependencies

- **cryptography**: For secure communication with Photoshop
- **jinja2**: For JavaScript template rendering
- **esprima** (optional dev): For JavaScript validation
- **pillow** (dev): For image handling in tests