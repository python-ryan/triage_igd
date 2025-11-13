from datetime import datetime
from db import conversation_col
from zoneinfo import ZoneInfo

local_tz = ZoneInfo("Asia/Makassar")


def save_conversation(wa_number: str, role: str, message: str):
    """Simpan percakapan ke MongoDB"""
    conversation_col.insert_one(
        {
            "wa_number": wa_number,
            "role": role,  # "user" atau "bot"
            "message": message,
            "timestamp": datetime.now(local_tz),
        }
    )


def get_history(wa_number: str):
    """Ambil riwayat percakapan dari MongoDB"""
    conv = conversation_col.find({"wa_number": wa_number}).sort("timestamp", 1)
    return [
        {
            "role": c["role"],
            "message": c["message"],
            "timestamp": c["timestamp"].isoformat(),
        }
        for c in conv
    ]
