import os
from openai import OpenAI
from conversation import save_conversation
from db import sessions
import json
import asyncio

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

2. Kamu akan selalu menjawab dalam format Markdown.
    Gunakan:
    - **bold** untuk penekanan
    - *italic* untuk istilah
    - - untuk daftar tidak berurut
    - 1. untuk daftar berurut
    - # Heading jika perlu
    - > untuk blockquote

3. Jika informasi pasien tidak cukup, jangan keluarkan klasifikasi, tapi tanyakan pertanyaan singkat yang relevan (misalnya: "Apakah pasien masih bernapas?").

4. Gunakan bahasa sehari-hari, tanpa istilah medis rumit, dan empatik. Contoh: "kesadaran menurun", diganti jadi "pasien sulit dibangunkan".

5. Jika informasi pasien sudah cukup, kembalikan juga klasifikasi akhir:
    [Emoji Warna] **<Nama Warna>** – <Keterangan kondisi singkat>
    [📊 **Level <X>**] – <Tindakan/urgensi singkat> ✅

6. Selalu sertakan anjuran tindakan. Bukan hanya klasifikasi, tapi juga apa yang harus segera dilakukan.

7. Tutup dengan kalimat ringkas(misalnya: “⚠️ Ini kondisi darurat, segera hubungi 119”).

Aturan klasifikasi:

{SOP_DOC}

Format keluaran:
- Jika klasifikasi final, selalu 2 baris, lalu akhiri dengan ✅
- Jika tanya balik, hanya pertanyaan singkat.
- blockquote jawaban final
"""


async def ask_stream_gpt(user_msg: str, session: dict, norm: str):
    input_messages = [
        {"role": "developer", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_msg},
    ]

    create_kwargs = {
        "model": "gpt-5-mini",
        "input": input_messages,
        "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "low"},
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
    sessions.update_one({"user_id": norm}, {"$set": session}, upsert=True)
    # simpan jawaban GPT ke MongoDB
    save_conversation(norm, "bot", bot_msg)

    for ch in bot_msg:
        payload = {"event": "message_chunk", "delta": ch}
        tokenFormat = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        yield tokenFormat
        await asyncio.sleep(0.05)

    yield f"data: {json.dumps({'event': 'stream_end'})}\n\n"
    yield "data: [DONE]\n\n"
