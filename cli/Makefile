BINARY_NAME=hyperclast
VERSION?=$(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
BUILD_TIME=$(shell date -u '+%Y-%m-%dT%H:%M:%SZ')
GIT_COMMIT=$(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Inject version info into the cmd package
LDFLAGS=-ldflags "-s -w \
	-X github.com/hyperclast/workspace/cli/cmd.Version=$(VERSION) \
	-X github.com/hyperclast/workspace/cli/cmd.BuildTime=$(BUILD_TIME) \
	-X github.com/hyperclast/workspace/cli/cmd.GitCommit=$(GIT_COMMIT)"

PLATFORMS=darwin-arm64 darwin-amd64 linux-amd64 linux-arm64 windows-amd64

.PHONY: all build build-all clean test install fmt lint deps release checksums

all: build

build:
	go build $(LDFLAGS) -o $(BINARY_NAME) .

# Build for all platforms
build-all: clean
	@mkdir -p dist
	@echo "Building $(VERSION) for all platforms..."
	@GOOS=darwin GOARCH=arm64 go build $(LDFLAGS) -o dist/$(BINARY_NAME)-darwin-arm64 .
	@GOOS=darwin GOARCH=amd64 go build $(LDFLAGS) -o dist/$(BINARY_NAME)-darwin-amd64 .
	@GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o dist/$(BINARY_NAME)-linux-amd64 .
	@GOOS=linux GOARCH=arm64 go build $(LDFLAGS) -o dist/$(BINARY_NAME)-linux-arm64 .
	@GOOS=windows GOARCH=amd64 go build $(LDFLAGS) -o dist/$(BINARY_NAME)-windows-amd64.exe .
	@echo "Done! Binaries in dist/"
	@ls -lh dist/

# Build and generate checksums for release
release: build-all checksums
	@echo ""
	@echo "Release $(VERSION) ready!"
	@echo "Files to upload to GitHub release:"
	@ls -1 dist/

checksums:
	@echo "Generating checksums..."
	@cd dist && shasum -a 256 $(BINARY_NAME)-* > checksums.txt
	@cat dist/checksums.txt

clean:
	rm -f $(BINARY_NAME)
	rm -rf dist/

test:
	go test -v ./...

install: build
	@echo "Installing to /usr/local/bin/$(BINARY_NAME)..."
	@sudo cp $(BINARY_NAME) /usr/local/bin/
	@echo "Done! Run 'hyperclast version' to verify."

uninstall:
	@sudo rm -f /usr/local/bin/$(BINARY_NAME)
	@echo "Uninstalled $(BINARY_NAME)"

fmt:
	go fmt ./...

lint:
	golangci-lint run

deps:
	go mod tidy
	go mod download

# Show version that would be built
version:
	@echo "Version: $(VERSION)"
	@echo "Commit:  $(GIT_COMMIT)"
	@echo "Time:    $(BUILD_TIME)"

# Create and push a new version tag
# Usage: make tag V=0.1.0
TAG_PREFIX=cli-v
tag:
ifndef V
	$(error Usage: make tag V=0.1.0)
endif
	@echo "Creating tag $(TAG_PREFIX)$(V)..."
	git tag -a $(TAG_PREFIX)$(V) -m "CLI Release v$(V)"
	@echo "Push with: git push origin $(TAG_PREFIX)$(V)"

# Create GitHub release and upload binaries (requires gh CLI)
# Usage: make github-release V=0.1.0
# Add FORCE=1 to skip version bump check
VERSION_TRACKING_FILE=.last-released-version
github-release:
ifndef V
	$(error Usage: make github-release V=0.1.0)
endif
	@if [ -f "$(VERSION_TRACKING_FILE)" ]; then \
		LAST_VERSION=$$(cat $(VERSION_TRACKING_FILE)); \
		if [ "$$LAST_VERSION" = "$(V)" ] && [ "$(FORCE)" != "1" ]; then \
			echo ""; \
			echo "⚠️  WARNING: Version $(V) was already released"; \
			echo "   Last released: $$LAST_VERSION"; \
			echo ""; \
			echo "   To release a new version, use a different V="; \
			echo "   To force re-release: make github-release V=$(V) FORCE=1"; \
			echo ""; \
			read -p "Release anyway? [y/N] " REPLY; \
			if [ "$$REPLY" != "y" ] && [ "$$REPLY" != "Y" ]; then \
				echo "Aborted."; \
				exit 1; \
			fi; \
		fi; \
	fi
	@echo "Creating GitHub release $(TAG_PREFIX)$(V)..."
	@if ! command -v gh &> /dev/null; then \
		echo "Error: GitHub CLI (gh) not installed. Install with: brew install gh"; \
		exit 1; \
	fi
	@VERSION=$(V) $(MAKE) release
	gh release create $(TAG_PREFIX)$(V) dist/* --title "CLI v$(V)" --generate-notes
	@echo "$(V)" > $(VERSION_TRACKING_FILE)
	@echo "Release $(TAG_PREFIX)$(V) published!"

# Full release workflow: tag + build + upload
# Usage: make full-release V=0.1.0
full-release:
ifndef V
	$(error Usage: make full-release V=0.1.0)
endif
	@echo "=== Full CLI Release Workflow for v$(V) ==="
	@$(MAKE) tag V=$(V)
	git push origin $(TAG_PREFIX)$(V)
	@$(MAKE) github-release V=$(V)
	@echo "=== CLI Release $(TAG_PREFIX)$(V) complete! ==="
