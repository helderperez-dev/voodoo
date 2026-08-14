#!/usr/bin/env bash
set -e

echo "🪄 Installing Voodoo Framework..."

INSTALL_DIR="$HOME/.voodoo"
BIN_DIR="$HOME/.local/bin"

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

echo "📦 Setting up isolated environment in $INSTALL_DIR/venv..."
if command -v uv &> /dev/null; then
    echo "⚡ Using uv for blazing fast installation..."
    rm -rf "$INSTALL_DIR/venv"
    uv venv "$INSTALL_DIR/venv"
    uv pip install --python "$INSTALL_DIR/venv" voodoo-framework
else
    if command -v python3 &> /dev/null; then
        rm -rf "$INSTALL_DIR/venv"
        python3 -m venv "$INSTALL_DIR/venv"
    elif command -v python &> /dev/null; then
        python -m venv "$INSTALL_DIR/venv"
    else
        echo "❌ Error: Python 3 is required but not found."
        exit 1
    fi
    "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    "$INSTALL_DIR/venv/bin/pip" install voodoo-framework
fi

echo "🔗 Linking executable to $BIN_DIR/voodoo..."
ln -sf "$INSTALL_DIR/venv/bin/voodoo" "$BIN_DIR/voodoo"

echo "✨ Voodoo is installed!"
echo ""
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo "⚠️  Please add $BIN_DIR to your PATH."
    echo "   Add this line to your ~/.zshrc or ~/.bashrc:"
    echo "   export PATH=\"$BIN_DIR:\$PATH\""
else
    echo "🚀 You can now run 'voodoo new my_app' from anywhere."
fi