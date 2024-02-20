#!/bin/bash

SCRIPT=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT")

rm -rf ./documentation
mkdir -p ./documentation
git clone git@github.com:Chainlit/docs.git

FILE_PATHS=$(find ./docs -name "*.mdx")

while IFS= read -r file; do
    cp "$file" ./documentation/
done <<< "$FILE_PATHS"

rm -rf ./docs

python3 "$SCRIPT_DIR/main.py"
