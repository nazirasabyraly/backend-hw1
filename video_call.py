from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, List
import json
import base64
import openai
from dotenv import load_dotenv
import os

load_dotenv()

class VideoCallManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        if room_id in self.active_connections:
            self.active_connections[room_id].remove(websocket)
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast(self, message: str, room_id: str, sender: WebSocket):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                if connection != sender:
                    await connection.send_text(message)

    async def process_video_frame(self, frame_data: str, room_id: str):
        try:
            # Decode base64 image
            image_data = base64.b64decode(frame_data.split(',')[1])
            
            # Process with OpenAI Vision API
            response = self.openai_client.chat.completions.create(
                model="gpt-4-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyze this image and provide a brief description."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{frame_data}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Error processing frame: {str(e)}"

manager = VideoCallManager() 