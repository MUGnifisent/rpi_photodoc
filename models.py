import json
import os
from flask import current_app # Added current_app for filepath
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

USER_DATA_FILE = 'config/users.json'  # Updated path

def get_user_data_path():
    return os.path.join(current_app.root_path, USER_DATA_FILE)

users = {} # This will now be populated from the file
next_user_id = 1

def load_users():
    global users, next_user_id
    try:
        with open(get_user_data_path(), 'r') as f:
            data = json.load(f)
            users_list = data.get('users', [])
            users = {int(u['id']): User(id=int(u['id']), username=u['username'], password_hash=u['password_hash']) for u in users_list}
            next_user_id = data.get('next_user_id', 1)
            if not users: # If users_list was empty or not found
                next_user_id = 1
            elif users:
                 # Ensure next_user_id is greater than any existing ID
                max_id = max(users.keys())
                next_user_id = max(next_user_id, max_id + 1)

    except (FileNotFoundError, json.JSONDecodeError):
        users = {}
        next_user_id = 1

def save_users():
    # Convert User objects to dictionaries for JSON serialization
    users_serializable = [{"id": u.id, "username": u.username, "password_hash": u.password_hash} for u in users.values()]
    data = {'users': users_serializable, 'next_user_id': next_user_id}
    with open(get_user_data_path(), 'w') as f:
        json.dump(data, f, indent=4)

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
        
        # Ensure next_user_id is unique if multiple users are created quickly or after loading
        while next_user_id in users:
             next_user_id +=1

        user = User(id=next_user_id, username=username, password_hash=generate_password_hash(password))
        users[next_user_id] = user
        next_user_id += 1
        save_users() # Save after creating a new user
        return user

# Initial load of users when the module is imported
# This needs the app context to know current_app.root_path, 
# so we will call it from app.py after app is created.
# load_users() 