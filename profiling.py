from pymongo import MongoClient
from db import sessions, conversation_col
from datetime import datetime
from zoneinfo import ZoneInfo
from conversation import save_conversation

local_tz = ZoneInfo("Asia/Makassar")


NODE_S1_FLOW = [
    {
        "id": "who",
        "text": "Siapa yang mengalami keluhan?",
        "options": ["Saya", "Orang lain"],
    },
    {
        "id": "age",
        "text": "Usia pasien?",
        "options": ["<5 th", "5–17 th", "18–59 th", "≥60 th"],
    },
    {
        "id": "gender",
        "text": "Jenis kelamin?",
        "options": ["Laki-laki", "Perempuan"],
    },
    {
        "id": "pregnant",
        "text": "Apakah pasien hamil?",
        "options": ["Ya", "Tidak", "Tidak tahu"],
        "condition": {"gender": "Perempuan", "age": "18–59 th"},
    },
]


def start_profiling(user_id):
    """Mulai Node S1 untuk user baru"""
    sessions.insert_one(
        {"user_id": user_id, "step": 0, "profile": {}, "completed": False}
    )
    first_q = NODE_S1_FLOW[0]
    return f"{first_q['text']}\nPilihan: {', '.join(first_q['options'])}"


def handle_profiling(user_id: str, message: str, session: dict):
    """Tangani jawaban user dan lanjut pertanyaan berikutnya"""
    step = session["step"]

    # simpan jawaban sebelumnya
    if step > 0 and step <= len(NODE_S1_FLOW):
        prev_q = NODE_S1_FLOW[step - 1]
        session["profile"][prev_q["id"]] = message

    # cek apakah sudah selesai
    if step >= len(NODE_S1_FLOW):
        session["completed"] = True
        conversation_col.insert_one(
            {
                "wa_number": user_id,
                "profile": session["profile"],
                "created_at": datetime.now(local_tz),
            }
        )
        bot_msg = "Profiling selesai ✅. Silakan jelaskan keluhan utama pasien."
        save_conversation(user_id, "bot", bot_msg)
        return bot_msg, session

    # ambil pertanyaan selanjutnya
    q = NODE_S1_FLOW[step]

    # cek condition
    if "condition" in q:
        cond = q["condition"]
        if not all(session["profile"].get(k) == v for k, v in cond.items()):
            session["step"] += 1
            return handle_profiling(user_id, message, session)  # skip pertanyaan

    # kirim pertanyaan
    bot_msg = f"{q['text']}\nPilihan: {', '.join(q['options'])}"
    session["step"] += 1
    save_conversation(user_id, "bot", bot_msg)

    return bot_msg, session
