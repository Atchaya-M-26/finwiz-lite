from pymongo import MongoClient
from bson.objectid import ObjectId
import os

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)

db = client["finwiz"]
users_collection = db.users
files_collection = db["files"]

def find_user_by_email(email):
    return users_collection.find_one({"email": email})

def create_user(name, email, password_hash):
    return users_collection.insert_one(
        {"name": name, "email": email, "password_hash": password_hash}
    )

def get_user_by_id(user_id):
    return users_collection.find_one({"_id": ObjectId(user_id)})

def save_file_record(user_id, filename, original_name):
    return files_collection.insert_one(
        {
            "user_id": ObjectId(user_id),
            "filename": filename,
            "original_name": original_name,
        }
    )

def get_files_for_user(user_id):
    return list(files_collection.find({"user_id": ObjectId(user_id)}))
