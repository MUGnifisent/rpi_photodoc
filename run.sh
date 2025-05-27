#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

PROJECT_DIR="." # Assuming the script is in the project root

cd "$PROJECT_DIR"

# 1. Check for virtual environment
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment 'venv' not found."
    echo "Please run the setup script first (e.g., setup_and_run.sh or update.sh)."
    exit 1
fi

# 2. Activate the virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# 3. Check for .flaskenv file
if [ ! -f ".flaskenv" ]; then
    echo "Warning: .flaskenv file not found. Creating a default one."
    echo "FLASK_APP=app.py" > .flaskenv
    echo "FLASK_ENV=development" >> .flaskenv
elif ! grep -q "FLASK_APP=app.py" .flaskenv; then
    echo "Warning: FLASK_APP not found in .flaskenv. Adding it."
    echo "FLASK_APP=app.py" >> .flaskenv
fi

# 4. Ensure config directories exist (app.py does this, but good for belt-and-suspenders)
if [ -f "app.py" ]; then # Only if app.py exists, to avoid error if run in wrong dir
    echo "Ensuring config directories exist (via app.py logic if it runs)..."
    # app.py creates these on startup, so just a note here
    # mkdir -p config/prompts # This would be redundant if app.py handles it
else
    echo "Warning: app.py not found in current directory. Cannot ensure config directories."
fi


# 5. Run the Flask application
echo "Starting Flask application on http://0.0.0.0:5000 ..."
echo "You can access the application by navigating to http://localhost:5000 in your browser."
echo "Press CTRL+C to stop the server."
flask run --host=0.0.0.0 --port=5000

# Deactivate virtual environment when script exits (though flask run will keep it active until CTRL+C)
echo "Flask server stopped."
deactivate 