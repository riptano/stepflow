#!/bin/bash
# Licensed to the Apache Software Foundation (ASF) under one or more contributor
# license agreements.  See the NOTICE file distributed with this work for
# additional information regarding copyright ownership.  The ASF licenses this
# file to you under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.


set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
BUMP_TYPE=""
CREATE_PR=false
TAG_MESSAGE=""

# Help function
show_help() {
    cat << EOF
Usage: $0 [OPTIONS] <major|minor|patch>

Prepare a Python SDK release by bumping version and generating changelog.

ARGUMENTS:
    <major|minor|patch>     Type of version bump to perform

OPTIONS:
    --pr                   Create PR after preparing changes (requires clean git state)
    --message "text"       Add a custom message to the changelog entry
    -h, --help             Show this help message

EXAMPLES:
    $0 patch               # Bump patch version locally (safe to run)
    $0 minor --pr          # Bump minor version and create PR
    $0 major --message "Major refactor with breaking changes"  # Add custom message
    $0 patch --pr --message "Bug fixes and improvements"       # Create PR with message

BEHAVIOR:
    By default, this script only updates local files:
    - Updates version in pyproject.toml
    - Updates uv.lock if present
    - Generates/updates CHANGELOG.md

    With --pr flag, it also:
    - Creates release branch
    - Commits changes
    - Pushes branch and creates PR

REQUIREMENTS:
    - git-cliff (for changelog generation)
    - uv (for Python dependency management)
    - gh CLI (only needed with --pr flag)
    - Clean git working directory (only needed with --pr flag)

EOF
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        major|minor|patch)
            if [[ -n "$BUMP_TYPE" ]]; then
                echo -e "${RED}Error: Multiple bump types specified${NC}" >&2
                exit 1
            fi
            BUMP_TYPE="$1"
            shift
            ;;
        --pr)
            CREATE_PR=true
            shift
            ;;
        --message)
            if [[ -n "${2-}" ]] && [[ ! "$2" =~ ^-- ]]; then
                TAG_MESSAGE="$2"
                shift 2
            else
                echo -e "${RED}Error: --message requires a value${NC}" >&2
                exit 1
            fi
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option '$1'${NC}" >&2
            echo "Use '$0 --help' for usage information." >&2
            exit 1
            ;;
    esac
done

# Validate bump type
if [[ -z "$BUMP_TYPE" ]]; then
    echo -e "${RED}Error: Version bump type is required${NC}" >&2
    echo "Use '$0 --help' for usage information." >&2
    exit 1
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check dependencies
echo -e "${BLUE}Checking dependencies...${NC}"
if ! command_exists git-cliff; then
    echo -e "${RED}Error: git-cliff is not installed${NC}" >&2
    echo "Install with: cargo install git-cliff" >&2
    exit 1
fi

if ! command_exists uv; then
    echo -e "${RED}Error: uv is not installed${NC}" >&2
    echo "Install from: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

if [[ "$CREATE_PR" == true ]] && ! command_exists gh; then
    echo -e "${RED}Error: gh CLI is not installed (required for --pr flag)${NC}" >&2
    echo "Install from: https://cli.github.com/" >&2
    exit 1
fi

# Ensure we're in the project root directory
if [[ ! -d "sdks/python" ]] || [[ ! -f "sdks/python/pyproject.toml" ]]; then
    echo -e "${RED}Error: Must be run from project root directory${NC}" >&2
    echo "Expected to find sdks/python/pyproject.toml" >&2
    exit 1
fi

# Change to Python SDK directory for operations
cd sdks/python

# Check git status only if creating PR
if [[ "$CREATE_PR" == true ]] && [[ -n "$(git status --porcelain)" ]]; then
    echo -e "${RED}Error: Working directory is not clean (required for --pr flag)${NC}" >&2
    echo "Please commit or stash your changes first, or run without --pr to prepare changes locally." >&2
    exit 1
fi

# Get current version from pyproject.toml
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/')
echo -e "${BLUE}Current version: ${GREEN}$CURRENT_VERSION${NC}"

# Calculate new version
IFS='.' read -ra VERSION_PARTS <<< "$CURRENT_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}

case "$BUMP_TYPE" in
    major)
        NEW_VERSION="$((MAJOR + 1)).0.0"
        ;;
    minor)
        NEW_VERSION="$MAJOR.$((MINOR + 1)).0"
        ;;
    patch)
        NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
        ;;
esac

echo -e "${BLUE}New version: ${GREEN}$NEW_VERSION${NC}"

# Update version in pyproject.toml
echo -e "${BLUE}Updating version in pyproject.toml...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/^version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
else
    # Linux
    sed -i "s/^version = \"$CURRENT_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
fi

# Update uv.lock if it exists
if [[ -f "uv.lock" ]]; then
    echo -e "${BLUE}Updating uv.lock...${NC}"
    if ! uv lock; then
        echo -e "${YELLOW}Warning: Failed to update uv.lock, continuing anyway...${NC}"
    fi
fi

# Generate changelog
echo -e "${BLUE}Generating changelog...${NC}"

# Check if CHANGELOG.md exists, create if not
if [[ ! -f "CHANGELOG.md" ]]; then
    echo -e "${YELLOW}Creating new CHANGELOG.md${NC}"
    cat > CHANGELOG.md << EOF
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

EOF
fi

# Generate changelog with git-cliff
echo -e "${BLUE}Generating changelog (Python SDK changes only)${NC}"
if [[ -n "$TAG_MESSAGE" ]]; then
    echo -e "${BLUE}Including custom message: ${GREEN}$TAG_MESSAGE${NC}"
    git-cliff --config cliff.toml --tag "stepflow-py-$NEW_VERSION" -u --prepend CHANGELOG.md --with-tag-message "$TAG_MESSAGE"
else
    git-cliff --config cliff.toml --tag "stepflow-py-$NEW_VERSION" -u --prepend CHANGELOG.md
fi

echo -e "${GREEN}✅ Release preparation complete!${NC}"
echo -e "${BLUE}Changes made:${NC}"
echo "  - Version bumped from $CURRENT_VERSION to $NEW_VERSION in pyproject.toml"
if [[ -f "uv.lock" ]]; then
    echo "  - Updated uv.lock"
fi
echo "  - Generated/updated CHANGELOG.md"

if [[ "$CREATE_PR" == false ]]; then
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Review the changes with: git diff"
    echo "2. If satisfied, create PR with: $0 $BUMP_TYPE --pr"
    echo "3. Or commit manually and push as needed"
    exit 0
fi

# Create PR workflow
echo ""
echo -e "${BLUE}Creating pull request...${NC}"

# Create release branch
RELEASE_BRANCH="release/stepflow-py-v$NEW_VERSION"
echo -e "${BLUE}Creating release branch: $RELEASE_BRANCH${NC}"
git checkout -b "$RELEASE_BRANCH"

# Commit changes
echo -e "${BLUE}Committing changes...${NC}"
if [[ -f "uv.lock" ]]; then
    git add pyproject.toml uv.lock CHANGELOG.md
else
    git add pyproject.toml CHANGELOG.md
fi
git commit -m "chore: release stepflow-py v$NEW_VERSION

- Bump version from $CURRENT_VERSION to $NEW_VERSION
- Update CHANGELOG.md with release notes"

# Push branch
echo -e "${BLUE}Pushing release branch...${NC}"
git push -u origin "$RELEASE_BRANCH"

# Create PR
PR_BODY="## Release stepflow-py v$NEW_VERSION

This PR prepares the release of stepflow-py v$NEW_VERSION.

### Changes
- Version bump from $CURRENT_VERSION to $NEW_VERSION
- Updated CHANGELOG.md with release notes

### Next Steps
1. Review the changelog entries
2. Merge this PR
3. The release will be automatically tagged and published to PyPI"

PR_URL=$(gh pr create \
    --title "chore: release stepflow-py v$NEW_VERSION" \
    --body "$PR_BODY" \
    --label "release" \
    --label "release:stepflow-py")

echo -e "${GREEN}✅ Release PR created successfully!${NC}"
echo -e "${BLUE}PR URL: $PR_URL${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Review the PR and changelog"
echo "2. Merge the PR when ready"
echo "3. The release will be automatically tagged and published to PyPI"