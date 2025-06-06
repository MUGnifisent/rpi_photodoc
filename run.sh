#!/bin/bash

#=============================================================================
#  APPLICATION RUNNER
#=============================================================================
# Starts the Flask application server

set -e

PROJECT_DIR="rpi_photodoc"

#-----------------------------------------------------------------------------
# Directory Navigation
#-----------------------------------------------------------------------------
if [ -d "$PROJECT_DIR" ] && [ "$(basename "$(pwd)")" != "$PROJECT_DIR" ]; then
    echo "📁 Changing to project directory: $PROJECT_DIR"
    cd "$PROJECT_DIR"
elif [ ! -d "venv" ] && [ -d "../$PROJECT_DIR/venv" ]; then
    echo "📁 Changing to project directory from parent: $PROJECT_DIR"
    cd "../$PROJECT_DIR"
fi

#-----------------------------------------------------------------------------
# Environment Check
#-----------------------------------------------------------------------------
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found"
    echo "   Please run './setup_and_run.sh' first"
    exit 1
fi

#-----------------------------------------------------------------------------
# Start Application
#-----------------------------------------------------------------------------
echo "🔄 Activating virtual environment..."
source venv/bin/activate

echo ""
echo "🚀 Starting Flask application..."
echo "   Access at: http://localhost:5000"
echo "   Press CTRL+C to stop"
echo ""

./venv/bin/python -m flask run --host=0.0.0.0 --port=5000

echo "🛑 Flask server stopped"
deactivate