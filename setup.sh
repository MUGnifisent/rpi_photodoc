#!/bin/bash

#=============================================================================
#  PROJECT SETUP SCRIPT
#=============================================================================
# Sets up the application environment and dependencies

set -e

REPO_URL="https://github.com/MUGnifisent/rpi_photodoc.git"
PROJECT_DIR="rpi_photodoc"

#-----------------------------------------------------------------------------
# System Dependencies
#-----------------------------------------------------------------------------
echo "🔧 Installing system dependencies..."
echo "   This may require sudo password."

if sudo apt update && sudo apt install -y git python3-venv python3.11-dev libcap-dev libcamera-apps python3-libcamera libssl-dev; then
    echo "✅ System dependencies installed"
else
    echo "❌ Failed to install system dependencies"
    exit 1
fi

#-----------------------------------------------------------------------------
# Repository Setup
#-----------------------------------------------------------------------------
if [ -d "$PROJECT_DIR" ]; then
    echo "📁 Updating existing repository..."
    cd "$PROJECT_DIR"
    git pull
    cd ..
else
    echo "📥 Cloning repository..."
    git clone "$REPO_URL" "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"

#-----------------------------------------------------------------------------
# Python Environment
#-----------------------------------------------------------------------------
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv --system-site-packages venv
else
    echo "🐍 Virtual environment exists"
fi

echo "🔄 Activating virtual environment..."
source venv/bin/activate

#-----------------------------------------------------------------------------
# Dependencies
#-----------------------------------------------------------------------------
echo "📦 Upgrading pip..."
pip3 install --upgrade pip

echo "📦 Installing dependencies..."
if pip3 install -r requirements.txt; then
    echo "✅ Dependencies installed"
else
    echo "❌ Failed to install dependencies"
    deactivate
    exit 1
fi

echo "🔧 Reinstalling cryptography and Werkzeug..."
if pip3 install --force-reinstall --no-cache-dir cryptography Werkzeug; then
    echo "✅ Security packages updated"
else
    echo "⚠️  Warning: Failed to reinstall security packages"
fi

#-----------------------------------------------------------------------------
# Configuration
#-----------------------------------------------------------------------------
if [ ! -f ".flaskenv" ]; then
    echo "⚙️  Creating Flask configuration..."
    echo "FLASK_APP=app.py" > .flaskenv
    echo "FLASK_ENV=development" >> .flaskenv
elif ! grep -q "FLASK_APP=app.py" .flaskenv; then
    echo "FLASK_APP=app.py" >> .flaskenv
    echo "⚙️  Updated Flask configuration"
fi

deactivate

echo ""
echo "✅ Setup complete!"
echo "🚀 Run 'bash run.sh' to start the application"