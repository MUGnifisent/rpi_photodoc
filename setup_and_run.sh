#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

REPO_URL="https://github.com/MUGnifisent/rpi_photodoc.git"
PROJECT_DIR="rpi_photodoc"

# 1. Clone the repository
if [ -d "$PROJECT_DIR" ]; then
    echo "Directory $PROJECT_DIR already exists. Pulling latest changes."
    cd "$PROJECT_DIR"
    git pull
    cd ..
else
    echo "Cloning repository $REPO_URL..."
    git clone "$REPO_URL"
fi

cd "$PROJECT_DIR"

# 2. Create a Python virtual environment
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment 'venv' already exists."
fi

# 3. Activate the virtual environment and install dependencies
echo "Activating virtual environment and installing dependencies..."
source venv/bin/activate
pip3 install --upgrade pip
pip3 install -r requirements.txt

# 4. Create .flaskenv file if it doesn't exist
if [ ! -f ".flaskenv" ]; then
    echo "Creating .flaskenv file..."
    echo "FLASK_APP=app.py" > .flaskenv
    echo "FLASK_ENV=development" >> .flaskenv
else
    echo ".flaskenv file already exists."
    # Ensure FLASK_APP is set
    if ! grep -q "FLASK_APP=app.py" .flaskenv; then
        echo "FLASK_APP=app.py" >> .flaskenv
    fi
fi

# Ensure config directories exist (app.py does this, but good for explicitness if running setup separately)
echo "Ensuring config directories exist..."
mkdir -p config/prompts

echo "Dependencies installed and environment configured."

# 5. Run the Flask application
echo "Starting Flask application on http://0.0.0.0:5000 ..."
echo "You can access the application by navigating to http://localhost:5000 in your browser."
flask run --host=0.0.0.0 --port=5000

# Deactivate virtual environment when script exits (though flask run will keep it active)
# This line might not be reached if flask run is foreground.
deactivate 