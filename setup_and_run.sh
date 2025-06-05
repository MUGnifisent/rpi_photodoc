#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

REPO_URL="https://github.com/MUGnifisent/rpi_photodoc.git"
PROJECT_DIR="rpi_photodoc"

# 0. Install System-level dependencies for picamera2 and building packages
# This requires sudo, so the user might be prompted for a password.
echo "Ensuring system dependencies for camera and Python builds are installed..."
echo "This may require sudo password."
if sudo apt update && sudo apt install -y git python3-venv python3.11-dev libcap-dev libcamera-apps python3-libcamera libssl-dev; then
    echo "System dependencies checked/installed."
else
    echo "Error: Failed to install system dependencies. Please check apt errors."
    exit 1
fi

# 1. Clone or update the repository
if [ -d "$PROJECT_DIR" ]; then
    echo "Directory '$PROJECT_DIR' already exists. Pulling latest changes..."
    cd "$PROJECT_DIR"
    git pull
    cd ..
else
    echo "Cloning repository from $REPO_URL..."
    git clone "$REPO_URL" "$PROJECT_DIR"
fi

cd "$PROJECT_DIR"

# 2. Create Python virtual environment with system-site-packages
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment 'venv' with --system-site-packages..."
    python3 -m venv --system-site-packages venv
else
    echo "Virtual environment 'venv' already exists."
fi

echo "Activating virtual environment..."
source venv/bin/activate

# 3. Upgrade pip and install dependencies
echo "Upgrading pip..."
pip3 install --upgrade pip

echo "Installing dependencies from requirements.txt..."
if pip3 install -r requirements.txt; then
    echo "Dependencies successfully installed."
else
    echo "Error: Failed to install dependencies from requirements.txt."
    echo "Please check for errors above."
    deactivate
    exit 1
fi

echo "Forcing reinstall of cryptography and Werkzeug to link with updated OpenSSL if necessary..."
if pip3 install --force-reinstall --no-cache-dir cryptography Werkzeug; then
    echo "Successfully reinstalled cryptography and Werkzeug."
else
    echo "Warning: Failed to force reinstall cryptography or Werkzeug. This might lead to issues if OpenSSL linking was problematic."
fi

# 4. Create .flaskenv file if it doesn't exist
if [ ! -f ".flaskenv" ]; then
    echo "Creating .flaskenv file..."
    echo "FLASK_APP=app.py" > .flaskenv
    echo "FLASK_ENV=development" >> .flaskenv
elif ! grep -q "FLASK_APP=app.py" .flaskenv; then
    echo "FLASK_APP=app.py" >> .flaskenv
    echo "Added FLASK_APP=app.py to .flaskenv"
fi

echo "Setup complete. Starting Flask server..."
# Ensure we use the virtual environment's Python and Flask
./venv/bin/python -m flask run --host=0.0.0.0 --port=5000

# Deactivate venv when server stops (though flask run might not return control here easily)
# This is more for cleanup if the script were to continue after flask run.
# In practice, Ctrl+C will stop flask run, and the script will end.
deactivate 