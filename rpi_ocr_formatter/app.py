import os
from flask import Flask
from flask_login import LoginManager
from routes import main_bp
from models import User

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'main.login'

@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)

app.register_blueprint(main_bp)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0') 