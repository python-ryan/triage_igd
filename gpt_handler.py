import os
from openai import OpenAI
from conversation import save_conversation
from db import sessions

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client_gpt = OpenAI(api_key=OPENAI_API_KEY)

# Load SOP text
with open("sop_triage.md", "r", encoding="utf-8") as f:
    SOP_DOC = f.read()

SYSTEM_INSTRUCTION = f"""
Anda adalah asisten triase kegawatdaruratan diRS dr. Wahidin Sudirohusodo.
Tugasmu hanya:
1. Ekstrak informasi pasien dalam bentuk list sederhana tapi jangan sertakan dalam jawaban:
    "sadar": "ya/tidak/tidak jelas",
    "napas": "normal/sulit/tidak",
    "nadi": "normal/lemah/berhenti"
    "perdarahan": "ya/tidak/tidak jelas",
    "nyeri": "ringan/berat/tidak ada/tidak jelas"

2. Tegaskan poin penting dengan bold (pakai *teks* agar terbaca di WhatsApp).

3. Jika informasi pasien tidak cukup, jangan keluarkan klasifikasi, tapi tanyakan pertanyaan singkat yang relevan (misalnya: "Apakah pasien masih bernapas?").

4. Gunakan bahasa sehari-hari, tanpa istilah medis rumit. Contoh: "kesadaran menurun", diganti jadi "pasien sulit dibangunkan".

5. Jika informasi pasien sudah cukup, kembalikan juga klasifikasi akhir:
    [Emoji Warna] *<Nama Warna>* – <Keterangan kondisi singkat>
    📊 *Level <X>* – <Tindakan/urgensi singkat> ✅

6. Selalu sertakan anjuran tindakan. Bukan hanya klasifikasi, tapi juga apa yang harus segera dilakukan. Tegaskan dengan bold (pakai *teks* agar terbaca di WhatsApp)

7. Tutup dengan kalimat ringkas, misalnya: “⚠️ Ini kondisi darurat, segera hubungi 119”

Aturan klasifikasi:

{SOP_DOC}

Format keluaran:
- Jika klasifikasi final, selalu 2 baris, lalu akhiri dengan ✅
- Jika tanya balik, hanya pertanyaan singkat.
"""


def ask_gpt(user_msg: str, session: dict, wa_number: str):
    """
    Mengirim pesan user ke GPT dan mendapatkan jawaban.
    session: dict yang berisi 'last_response_id'
    Returns: bot_msg, updated_session
    """

    input_messages = [
        {"role": "developer", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_msg},
    ]

    create_kwargs = {
        "model": "gpt-5-mini",
        "input": input_messages,
        "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "medium"},
    }

    if session.get("last_response_id"):
        create_kwargs["previous_response_id"] = session["last_response_id"]

    response = client_gpt.responses.create(**create_kwargs)

    # gabungkan teks output
    bot_msg = ""
    for item in getattr(response, "output", []):
        # each 'item' typically has .content (list)
        contents = getattr(item, "content", None)
        if not contents:
            continue
        for c in contents:
            t = getattr(c, "text", None)
            if t:
                bot_msg += t

    # # update last_response_id
    session["last_response_id"] = response.id
    sessions.update_one({"user_id": wa_number}, {"$set": session}, upsert=True)
    # simpan jawaban GPT ke MongoDB
    save_conversation(wa_number, "bot", bot_msg)
    return bot_msg.strip()
