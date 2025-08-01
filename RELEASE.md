# Release Process

This document describes how to perform releases and how the release machinery works for the StepFlow project.

## How to Perform a Release

### Using GitHub Actions (Recommended)

1. **Navigate to GitHub Actions**
   - Go to the **Actions** tab in the GitHub repository
   - Select the **"Prepare Release"** workflow

2. **Trigger the Release**
   - Click **"Run workflow"**
   - Select inputs:
     - **Package**: `stepflow-rs` or `python-sdk`
     - **Bump type**: `patch`, `minor`, or `major`
     - **Message**: (Optional) Custom message for the changelog entry
   - Click **"Run workflow"**

3. **Review and Merge**
   - The workflow will create a release PR with:
     - Version bump in `Cargo.toml` and `Cargo.lock`
     - Updated `CHANGELOG.md` with changes since last release
   - Review the PR for accuracy
   - Merge the PR when ready

4. **Automatic Release**
   - Upon merge, a git tag is automatically created (`stepflow-rs-X.Y.Z` or `stepflow-py-X.Y.Z`)
   - The appropriate release workflow builds and publishes the package

### Package-Specific Release Information

#### Rust Package (`stepflow-rs`)
- **Output**: Multi-platform binaries, Docker images, GitHub release
- **Tag Format**: `stepflow-rs-X.Y.Z`
- **Artifacts**: Compiled binaries for Linux, macOS, Windows; Docker images

#### Python SDK (`python-sdk`)
- **Output**: PyPI package, GitHub release
- **Tag Format**: `stepflow-py-X.Y.Z`
- **Publishing**: PyPI via Trusted Publishing (no tokens required)
- **Artifacts**: Python wheel and source distribution

## How Releases Are Implemented

### Architecture Overview

```
    ┌─────────┐     ┌──────────────────┐     ┌───────────┐     ┌─────────┐
(1) │ Prepare │ (2) │ Release PR       │ (3) │ Release   │ (4) │ Build + │
───▶│ Manual  │────▶│ Creation         │────▶│ Dispatch  │────▶│ Tag +   │
    │ trigger │     │ (labeled PR)     │     │           │     │ Release │
    └─────────┘     └──────────────────┘     └───────────┘     └─────────┘

(1) "Release - Prepare" workflow (release_prepare.yml) is manually triggered.
(2) "Release - Prepare" pushes a Release PR with labels.
(3) "Release - Dispatch" workflow (release_dispatch.yml) is triggered when PR merges.
(4) "Release - Dispatch" triggers "Release - Rust" workflow (release_rust.yml).
```

### Workflow and Script Integration

#### 1. Release Preparation Script
**Location**: `stepflow-rs/scripts/prepare-release.sh`

**Core Logic:**
- Validates current git state and dependencies
- Bumps version in `Cargo.toml` (major/minor/patch)
- Updates `Cargo.lock` via `cargo check`
- Generates changelog using `git-cliff` with path filtering
- Validates that relevant changes exist for stepflow-rs
- Optionally creates git branch, commits, and GitHub PR

#### 2. GitHub Actions Workflows

**`release_prepare.yml`** - Release PR Creation
- **Trigger**: Manual `workflow_dispatch`
- **Process**:
  1. Installs dependencies (`git-cliff`)
  2. Runs `prepare-release.sh` with `--pr` flag
  3. Script creates labeled PR (`release`, `release:stepflow-rs`)

**`release_dispatch.yml`** - Release Detection and Dispatch
- **Trigger**: PR merge to `main` with `release:stepflow-rs` label
- **Process**:
  1. Extracts version from merged `stepflow-rs/Cargo.toml`
  2. Dispatches repository event to trigger release build
  3. Uses default `GITHUB_TOKEN` (no secrets needed)

**`release_rust.yml`** - Complete Release Process
- **Trigger**: Repository dispatch event `build-release` OR manual `workflow_dispatch`
- **Process**:
  1. Builds binaries and Docker images
  2. Verifies all artifacts
  3. Creates git tag and GitHub release atomically (only after successful build)
- **Manual Testing**: Can be run with `skip_tag_creation=true` for testing

#### 3. Changelog Generation
**Configuration**: `stepflow-rs/cliff.toml`

**Path Filtering** (Monorepo Support):
```toml
include_path = [
    "stepflow-rs/**",           # Main package
    "CLAUDE.md",                # Project docs
    "CONTRIBUTING.md",
    "README.md",
    ".github/workflows/release_rust.yml",  # Release-related workflows
    ".github/workflows/ci.yml"
]
```

**Features**:
- Conventional commit parsing and grouping
- GitHub PR link generation
- Only includes commits affecting stepflow-rs
- Generates changes since last `stepflow-rs-*` tag
- **Custom release messages**: Add descriptive text to changelog entries using `--message` flag

### Local Testing and Verification

The release scripts can be tested locally without creating PRs or tags:

#### Testing Version Bump and Changelog Generation

**Rust Package:**
```bash
# Test patch release locally (safe - no commits/PRs)
./scripts/prepare-release-rust.sh patch

# Test with custom message
./scripts/prepare-release-rust.sh patch --message "Critical security fixes and performance improvements"

# Review what changed
git diff

# Reset changes to test again
git checkout -- stepflow-rs/Cargo.toml stepflow-rs/Cargo.lock stepflow-rs/CHANGELOG.md
```

**Python SDK:**
```bash
# Test patch release locally (safe - no commits/PRs)
./scripts/prepare-release-python.sh patch

# Test with custom message
./scripts/prepare-release-python.sh patch --message "Bug fixes and improvements"

# Review what changed
git diff

# Reset changes to test again
git checkout -- sdks/python/pyproject.toml sdks/python/uv.lock sdks/python/CHANGELOG.md
```

#### Testing Different Bump Types

**Rust Package:**
```bash
# Test minor version bump
./scripts/prepare-release-rust.sh minor
git diff
git checkout -- stepflow-rs/Cargo.toml stepflow-rs/Cargo.lock stepflow-rs/CHANGELOG.md

# Test major version bump
./scripts/prepare-release-rust.sh major
git diff
git checkout -- stepflow-rs/Cargo.toml stepflow-rs/Cargo.lock stepflow-rs/CHANGELOG.md
```

**Python SDK:**
```bash
# Test minor version bump
./scripts/prepare-release-python.sh minor
git diff
git checkout -- sdks/python/pyproject.toml sdks/python/uv.lock sdks/python/CHANGELOG.md

# Test major version bump
./scripts/prepare-release-python.sh major
git diff
git checkout -- sdks/python/pyproject.toml sdks/python/uv.lock sdks/python/CHANGELOG.md
```

#### Verifying Changelog Generation

```bash
# Check what the last tag is
git describe --tags --abbrev=0 --match="stepflow-rs-*"

# Test changelog generation manually
git-cliff --config stepflow-rs/cliff.toml --tag "stepflow-rs-0.2.0" --range "stepflow-rs-0.1.0..HEAD"

# Preview what would be included (dry run)
git-cliff --config stepflow-rs/cliff.toml --unreleased
```

#### Testing PR Creation (Requires Clean Git State)

```bash
# Create a test branch first
git checkout -b test-release-script

# Test full PR creation flow
./scripts/prepare-release.sh patch --pr

# This will:
# 1. Create release branch
# 2. Commit changes
# 3. Push branch
# 4. Create GitHub PR with labels

# Clean up test
git checkout main
git branch -D test-release-script
# Delete the remote branch and PR manually
```

#### Testing Complete Release Flow

**Rust Package:**
```bash
# Test the entire release process without creating tags/releases
# Go to Actions → Release Rust → Run workflow
# Inputs:
#   version: 1.2.3-test
#   skip_tag_creation: true

# This will:
# 1. Build all binaries and Docker images
# 2. Verify artifacts work correctly
# 3. Skip tag and release creation
```

**Python SDK:**
```bash
# Test the entire release process without publishing to PyPI
# Go to Actions → Release Python SDK → Run workflow
# Inputs:
#   version: 1.2.3-test
#   skip_tag_creation: true

# This will:
# 1. Build Python wheel and source distribution
# 2. Run comprehensive tests
# 3. Skip PyPI publishing and tag creation
```

#### Validating Path Filtering

```bash
# Check which commits would be included
git log --oneline stepflow-rs-0.1.0..HEAD -- stepflow-rs/ CLAUDE.md CONTRIBUTING.md README.md .github/workflows/release_rust.yml .github/workflows/ci.yml

# Test that non-stepflow-rs changes are excluded
# (Make changes to sdks/ or docs/ directories and verify they don't appear)
```

### Dependencies for Local Testing

**Common Tools:**
- `git-cliff`: `cargo install git-cliff`
- `gh` CLI: Required only for `--pr` flag (https://cli.github.com/)

**Rust Package Additional Requirements:**
- Rust toolchain (stable)
- `cargo` for dependency management

**Python SDK Additional Requirements:**
- `uv`: Package manager (https://docs.astral.sh/uv/getting-started/installation/)
- Python 3.13+ (automatically installed by uv)

**Environment:**
- Clean git working directory (for `--pr` flag)
- Appropriate GitHub permissions (for PR creation)

### Troubleshooting Local Testing

**"No changes found affecting stepflow-rs"**
- Ensure commits exist that modify files in the `include_path`
- Check conventional commit format compliance
- Verify tag detection: `git describe --tags --abbrev=0 --match="stepflow-rs-*"`

**Script fails with permission errors**
- Ensure script is executable: `chmod +x scripts/prepare-release.sh`
- For PR creation, ensure `gh auth login` is completed

**Changelog is empty or incorrect**
- Test git-cliff configuration directly
- Check that commits follow conventional commit format
- Verify include_path patterns in `cliff.toml`

### Future Multi-Package Support

The system is designed to be extensible for additional packages (Python SDK, TypeScript SDK, etc.):

**To add a new package:**
1. Add package option to `release_prepare.yml` workflow inputs
2. Create package-specific release script or extend existing script
3. Add package-specific label handling in `release_tag.yml`
4. Create package-specific `cliff.toml` configuration if needed
5. Update documentation with new package procedures