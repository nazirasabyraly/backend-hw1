from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from assistant.info_agent import info_agent
from assistant.openai_assistant import ask_openai
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.future import select
from dotenv import load_dotenv
import os
from video_call import manager
import json
from io import BytesIO
from voice_handler import voice_handler
import base64

# .env
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# SQLAlchemy setup
Base = declarative_base()
engine = create_async_engine(DATABASE_URL, echo=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Dependency
async def get_session():
    async with AsyncSessionLocal() as session:
        yield session

# SQLAlchemy model
class ItemModel(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    description = Column(String, nullable=True)

# Pydantic models
class Item(BaseModel):
    id: int
    name: str
    description: Optional[str] = None

    class Config:
        orm_mode = True

class ChatRequest(BaseModel):
    messages: List[str]
    strategy: str = "alternate"

class AskRequest(BaseModel):
    prompt: str
    agent: str = "main"

# FastAPI app
app = FastAPI(debug=True)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to the API"}

# Voice chat endpoints
@app.get("/voice-chat", response_class=HTMLResponse)
async def voice_chat_page():
    print("Accessing voice-chat page")  # Debug info
    return FileResponse(os.path.join(BASE_DIR, "voice_chat.html"))

@app.post("/voice-chat")
async def voice_chat(audio_file: UploadFile = File(...)):
    try:
        # Read audio file
        audio_data = await audio_file.read()
        
        # Convert speech to text
        text = voice_handler.speech_to_text(audio_data)
        if text.startswith("Error"):
            raise HTTPException(status_code=400, detail=text)
        
        # Get AI response
        ai_response = voice_handler.get_ai_response(text)
        if ai_response.startswith("Error"):
            raise HTTPException(status_code=500, detail=ai_response)
        
        # Convert AI response to speech
        audio_response = voice_handler.text_to_speech(ai_response)
        if not audio_response:
            raise HTTPException(status_code=500, detail="Error generating speech response")
        
        return StreamingResponse(
            BytesIO(audio_response),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=response.mp3"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Video call endpoints
@app.get("/video-call", response_class=HTMLResponse)
async def video_call_page():
    print("Accessing video-call page")  # Debug info
    return FileResponse(os.path.join(BASE_DIR, "video_call.html"))

@app.websocket("/ws/video/{room_id}")
async def video_call_endpoint(websocket: WebSocket, room_id: str):
    await manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                ai_analysis = await manager.process_video_frame(data, room_id)
                await manager.broadcast(data, room_id, websocket)
                await websocket.send_text(json.dumps({
                    "type": "ai_analysis",
                    "content": ai_analysis
                }))
            except Exception as e:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "content": str(e)
                }))
    except WebSocketDisconnect:
        manager.disconnect(websocket, room_id)
        await manager.broadcast(json.dumps({
            "type": "system",
            "content": "A participant has left the call"
        }), room_id, websocket)

# AI endpoints
@app.post("/ask")
def ask(request: AskRequest):
    if request.agent == "info":
        answer = info_agent(request.prompt)
    else:
        answer = ask_openai(request.prompt)
    return {"response": answer}

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    response_log = []
    agents = {"main": ask_openai, "info": info_agent}
    
    for idx, message in enumerate(request.messages):
        if request.strategy == "alternate":
            agent = ask_openai if idx % 2 == 0 else info_agent
        else:
            agent = agents.get(request.strategy, ask_openai)

        reply = agent(message)
        response_log.append({"agent": "info" if agent == info_agent else "main", "response": reply})

    return {"chat": response_log}

# Task endpoints
@app.get("/task/")
async def run_task():
    return {"task_id": "667e7a72-4cd6-4fe9-94f4-466fa575dcb1"}

@app.get("/cache-example/")
async def cache_example():
    return {"message": "This is a cached response"}

# Database endpoints
@app.post("/items/", response_model=Item)
async def create_item(item: Item, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ItemModel).where(ItemModel.id == item.id))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Item already exists")

    new_item = ItemModel(**item.dict())
    session.add(new_item)
    await session.commit()
    await session.refresh(new_item)
    return new_item

@app.get("/items/", response_model=List[Item])
async def read_items(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ItemModel))
    return result.scalars().all()

@app.get("/items/{item_id}", response_model=Item)
async def read_item(item_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ItemModel).where(ItemModel.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.put("/items/{item_id}", response_model=Item)
async def update_item(item_id: int, updated: Item, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ItemModel).where(ItemModel.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.name = updated.name
    item.description = updated.description
    await session.commit()
    await session.refresh(item)
    return item

@app.delete("/items/{item_id}")
async def delete_item(item_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(ItemModel).where(ItemModel.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    await session.delete(item)
    await session.commit()
    return {"message": "Item deleted"}

# WebSocket для голосового чата
@app.websocket("/ws/voice")
async def voice_chat_websocket(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            try:
                # Парсим JSON данные
                message = json.loads(data)
                if message["type"] == "audio":
                    # Декодируем base64 аудио
                    audio_data = base64.b64decode(message["data"])
                    
                    # Конвертируем в текст
                    text = voice_handler.speech_to_text(audio_data)
                    if text.startswith("Error"):
                        await websocket.send_json({
                            "type": "error",
                            "text": text
                        })
                        continue
                    
                    # Отправляем распознанный текст
                    await websocket.send_json({
                        "type": "transcription",
                        "text": text
                    })
                    
                    # Получаем ответ от AI
                    ai_response = voice_handler.get_ai_response(text)
                    if ai_response.startswith("Error"):
                        await websocket.send_json({
                            "type": "error",
                            "text": ai_response
                        })
                        continue
                    
                    # Конвертируем ответ в речь
                    audio_response = voice_handler.text_to_speech(ai_response)
                    if not audio_response:
                        await websocket.send_json({
                            "type": "error",
                            "text": "Error generating speech response"
                        })
                        continue
                    
                    # Отправляем ответ
                    await websocket.send_json({
                        "type": "response",
                        "text": ai_response,
                        "audio": base64.b64encode(audio_response).decode()
                    })
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "text": str(e)
                })
    except WebSocketDisconnect:
        print("Client disconnected")

# Startup event
#@app.on_event("startup")
#async def startup():
#    async with engine.begin() as conn:
#        await conn.run_sync(Base.metadata.create_all)
#
