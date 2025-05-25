from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# In a real application, you would use a database like SQLAlchemy
# For simplicity, we'll use an in-memory dictionary for users.
users = {}
next_user_id = 1

class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def get(user_id):
        return users.get(int(user_id))

    @staticmethod
    def get_by_username(username):
        for user in users.values():
            if user.username == username:
                return user
        return None

    @staticmethod
    def create(username, password):
        global next_user_id
        if User.get_by_username(username):
            return None # User already exists
        user = User(id=next_user_id, username=username, password_hash=generate_password_hash(password))
        users[next_user_id] = user
        next_user_id += 1
        return user 