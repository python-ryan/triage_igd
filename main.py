import os
from fastapi import FastAPI, Request
from fastapi.responses import Response, JSONResponse, StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
from db import sessions, conversation_col
from conversation import save_conversation
from gpt_handler import ask_gpt, SYSTEM_INSTRUCTION
from gpt_stream_handle import ask_stream_gpt
import asyncio
import json

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise RuntimeError("Masukkan OPENAI_API_KEY didalam .env file")

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI(title="Triage IGD RSWS")

# simple session store (in-memory). In production ganti dengan DB.
session_map = {}  # user_id -> previous_response_id


class ChatReq(BaseModel):
    user_id: str
    message: str


class SessionId(BaseModel):
    user_id: str


class StreamMessage(BaseModel):
    user_id: int
    message: str


async def stream_opening(user_id: str):
    opening_msg = (
        "Halo 👋, saya Asisten Triase IGD 24/7 RSWS.\n"
        "Saya akan menanyakan beberapa pertanyaan untuk menilai kegawatan.\n"
        "Saya akan memberikan jawaban sesuai dengan SOP IGD RSWS\n"
        "Jawaban yang saya berikan bukan diagnosis dan tidak menggantikan dokter.\n\n"
        "Lanjutkan dengan memberitahu saya kondisi Anda saat ini"
    )
    save_conversation(user_id, "bot", opening_msg)
    await asyncio.sleep(0.05)
    for ch in opening_msg:
        payload = {"event": "message_chunk", "delta": ch}
        tokenFormat = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        yield tokenFormat
        await asyncio.sleep(0.01)

    yield f"data: {json.dumps({'event': 'stream_end'})}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/chat")
def chat(req: ChatReq):
    prev_id = session_map.get(req.user_id)

    # Build input; use a system developer message + user message
    input_messages = [
        {"role": "developer", "content": SYSTEM_INSTRUCTION},
        {"role": "user", "content": req.message},
    ]

    # Build kwargs for Responses API
    create_kwargs = {
        "model": "gpt-5-mini",  # atau "gpt-5-mini" / "gpt-5-nano" sesuai kebutuhan
        "input": input_messages,
        # speed/behavior controls: minimal reasoning + terse output for deterministic classification
        "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "medium"},
    }

    if prev_id:
        create_kwargs["previous_response_id"] = prev_id

    # Call Responses API
    response = client.responses.create(**create_kwargs)

    # Extract text body by concatenating response.output[*].content[*].text
    output_text = ""
    for item in getattr(response, "output", []):
        # each 'item' typically has .content (list)
        contents = getattr(item, "content", None)
        if not contents:
            continue
        for c in contents:
            t = getattr(c, "text", None)
            if t:
                output_text += t

    # save session
    session_map[req.user_id] = response.id

    return {"ai": output_text.strip(), "response_id": response.id}


@app.post("/reset_session")
def reset(req: SessionId):
    session_map.pop(req.user_id, None)
    return {"ok": True}


@app.get("/history/{wa_number}")
def get_history(wa_number: str):
    """Ambil riwayat percakapan berdasarkan nomor WhatsApp"""
    conv = conversation_col.find({"wa_number": wa_number}).sort("timestamp", 1)
    history = [
        {
            "role": c["role"],
            "message": c["message"],
            "timestamp": c["timestamp"].isoformat(),
        }
        for c in conv
    ]
    return {"wa_number": wa_number, "history": history}


@app.post("/stream/chat")
async def chat(request: StreamMessage):

    user_id = request.user_id
    usr_msg = request.message

    print(f"{user_id}, {usr_msg}")

    session = sessions.find_one({"user_id": user_id})
    new_session = False
    # ===== Profiling Node S1 =====
    if not session:
        session = {"user_id": user_id, "completed": True, "last_response_id": ""}
        sessions.insert_one(session)
        new_session = True

    if new_session:
        opening = stream_opening(user_id)
        return StreamingResponse(opening, media_type="text/event-stream")

    generator = ask_stream_gpt(usr_msg, session, user_id)
    return StreamingResponse(generator, media_type="text/event-stream")


@app.get("/")
def getVersion():
    return "Welcome to Ai IGD"
