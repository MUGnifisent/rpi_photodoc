#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

PROJECT_DIR="rpi_photodoc"

# Assuming the script is run from the parent directory of rpi_photodoc
# or that rpi_photodoc is in the current path.
# If not, cd to the specific project directory if needed.
# Example: cd "$(dirname "$0")/$PROJECT_DIR" if script is outside and knows relative path
# For now, assuming it's run from within rpi_photodoc or rpi_photodoc is directly under where it's run

if [ -d "$PROJECT_DIR" ] && [ "$(basename "$(pwd)")" != "$PROJECT_DIR" ]; then
  echo "Changing to project directory: $PROJECT_DIR"
  cd "$PROJECT_DIR"
elif [ ! -d "venv" ] && [ -d "../$PROJECT_DIR/venv" ]; then
    # This case is if the script is in a scripts/ folder one level up from rpi_photodoc
    echo "Changing to project directory from parent: $PROJECT_DIR"
    cd .. # assuming script is in a subfolder like 'scripts', go up
    cd "$PROJECT_DIR"
fi


if [ ! -d "venv" ]; then
    echo "Error: Virtual environment 'venv' not found."
    echo "Please run the setup script (e.g., setup_and_run.sh or update.sh) first."
    exit 1
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Ensuring config directories exist (via app.py logic if it runs)..."
echo "Starting Flask application on http://0.0.0.0:5000 ..."
echo "You can access the application by navigating to http://localhost:5000 in your browser."
echo "Press CTRL+C to stop the server."

# Use the python from the venv to run flask
python3 -m flask run --host=0.0.0.0 --port=5000

# Deactivate virtual environment when script exits
# This line will be reached if flask run exits gracefully or is interrupted.
echo "Flask server stopped. Deactivating virtual environment."
deactivate 