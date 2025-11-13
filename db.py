import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27018")
client = MongoClient(MONGO_URI)
db = client["triage"]

# Collections
sessions = db["sessions"]  # simpan session + last_response_id + profiling
conversation_col = db["conversations"]  # simpan semua chat log
