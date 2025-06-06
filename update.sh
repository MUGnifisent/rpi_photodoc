#!/bin/bash

#=============================================================================
#  APPLICATION UPDATER
#=============================================================================
# Updates the application with latest code and dependencies

set -e

#-----------------------------------------------------------------------------
# System Dependencies
#-----------------------------------------------------------------------------
echo "🔧 Updating system dependencies..."
echo "   This may require sudo password."

if sudo apt update && sudo apt install -y python3.11-dev libcap-dev libcamera-apps python3-libcamera libssl-dev; then
    echo "✅ System dependencies updated"
else
    echo "❌ Failed to update system dependencies"
    exit 1
fi

#-----------------------------------------------------------------------------
# Code Update
#-----------------------------------------------------------------------------
echo "📥 Pulling latest changes..."
if git pull; then
    echo "✅ Code updated"
else
    echo "⚠️  Git pull failed - resolve conflicts manually"
fi

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
# Dependencies Update
#-----------------------------------------------------------------------------
echo "📦 Upgrading pip..."
pip3 install --upgrade pip

echo "📦 Updating dependencies..."
if pip3 install -r requirements.txt; then
    echo "✅ Dependencies updated"
else
    echo "❌ Failed to update dependencies"
    deactivate
    exit 1
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
echo "✅ Update complete!"
echo "🚀 Run 'bash run.sh' to start the application"