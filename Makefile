.PHONY: test build deploy deploy-local install clean

# Default: run all tests
test:
	pip install -e ".[dev]" && pytest tests/ -v

# E2E test — full flow simulation
test-e2e:
	pip install -e ".[dev,mcp]" && pytest tests/test_e2e.py -v

# Install all deps
install:
	pip install -e ".[dev,mcp,cli,api,x402]"

# Build Rust core
build:
	cd crates/agentsafe-core && cargo build --release

# Deploy to Base Mainnet
deploy:
	pip install -e ".[dev]" && python scripts/deploy.py base

# Deploy to local Anvil (for testing)
deploy-local:
	pip install -e ".[dev]" && python scripts/deploy.py local

# Start MCP server
mcp:
	pip install -e ".[mcp]" && python -m agentsafe.mcp.server

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info/
	cd crates/agentsafe-core && cargo clean
