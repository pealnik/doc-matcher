#!/bin/bash
# Quick setup script for PDF Compliance Checker

set -e

echo "======================================================================"
echo "PDF Compliance Checker - Setup"
echo "======================================================================"

# Check Python
if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
elif command -v python &>/dev/null; then
    PYTHON_CMD=python
else
    echo "❌ Python not found. Install Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION"

# Check version
PYTHON_MAJOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$($PYTHON_CMD -c 'import sys; print(sys.version_info.minor)')
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo "❌ Python 3.8+ required. Found $PYTHON_VERSION"
    exit 1
fi

# Create venv if doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate and install
echo "Installing dependencies..."
source venv/bin/activate
pip install --upgrade pip setuptools wheel -q
pip install -r requirements.txt

echo ""
echo "======================================================================"
echo "✅ Setup complete!"
echo "======================================================================"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env:"
echo "   cp .env.example .env"
echo ""
echo "2. Edit .env and add your API keys"
echo ""
echo "3. Activate venv and run:"
echo "   source venv/bin/activate"
echo "   python pdf_compliance_checker.py --help"
echo "======================================================================"
