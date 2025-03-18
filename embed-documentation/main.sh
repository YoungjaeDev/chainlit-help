#!/bin/bash

SCRIPT=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT")

rm -rf ./cookbooks ./documentation
mkdir -p ./cookbooks ./documentation

git clone git@github.com:Chainlit/docs.git
git clone git@github.com:Chainlit/cookbook.git

# Use *.mdx from documentation and README.md, *.py from cookbook
# Modified to rename .mdx to .md during copying
find ./docs -name "*.mdx" -exec bash -c 'newname="./documentation/$(echo {} | sed "s|/|_|g" | sed "s|\.mdx$|\.md|")"; cp "{}" "$newname"' \;
find ./cookbook \( -name "*.py" \) -exec bash -c 'newname="./cookbooks/$(echo {} | sed "s|/|_|g")"; cp "{}" "$newname"' \;

rm -rf ./docs
rm -rf ./cookbook