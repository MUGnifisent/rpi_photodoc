#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Assuming the script is run from within the project directory (e.g. rpi_photodoc)
# Or, if you want it to be runnable from outside, you might need to specify PROJECT_DIR
# For simplicity, let's assume it's run from the project root.

echo "Updating the application..."

# 0. Install System-level dependencies for picamera2 and building packages
# This requires sudo, so the user might be prompted for a password.
echo "Ensuring system dependencies for camera and Python builds are installed..."
echo "This may require sudo password."
if sudo apt update && sudo apt install -y python3.11-dev libcap-dev libcamera-apps python3-libcamera; then
    echo "System dependencies checked/installed."
else
    echo "Error: Failed to install system dependencies. Please check apt errors."
    exit 1
fi

# 1. Pull latest changes from Git
echo "Pulling latest changes from Git repository..."
if git pull; then
    echo "Successfully pulled latest changes."
else
    echo "Warning: 'git pull' failed. This might be because you have local changes, or other Git issues."
    echo "Please resolve any Git conflicts or issues manually."
    # Optionally, you could add a `exit 1` here if a failed pull is critical
fi

# 2. Create/Activate Python virtual environment with system-site-packages
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment 'venv' with --system-site-packages..."
    python3 -m venv --system-site-packages venv
else
    echo "Virtual environment 'venv' already exists."
fi

echo "Activating virtual environment..."
source venv/bin/activate

# 3. Upgrade pip and install/update dependencies
echo "Upgrading pip..."
pip3 install --upgrade pip

echo "Installing/updating dependencies from requirements.txt..."
if pip3 install -r requirements.txt; then
    echo "Dependencies successfully installed/updated."
else
    echo "Error: Failed to install/update dependencies from requirements.txt."
    echo "Please check for errors above. You might need to resolve them manually."
    deactivate # Deactivate venv if pip install fails
    exit 1
fi

# 4. Ensure .flaskenv file is sensible (optional, but good practice)
if [ ! -f ".flaskenv" ]; then
    echo "Creating default .flaskenv file..."
    echo "FLASK_APP=app.py" > .flaskenv
    echo "FLASK_ENV=development" >> .flaskenv
elif ! grep -q "FLASK_APP=app.py" .flaskenv; then
    echo "FLASK_APP=app.py" >> .flaskenv
    echo "Added FLASK_APP=app.py to .flaskenv"
fi

# The app.py itself handles creation of config/prompts directories on startup.
# So, no explicit need to do it here unless desired for other reasons.


deactivate
echo "Update script finished."
echo "You can now run the application using './run.sh' or 'flask run' (after activating venv)."
