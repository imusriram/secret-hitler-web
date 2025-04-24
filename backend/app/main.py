# backend/app/main.py
import uvicorn
import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import users as user_api
from app.api import lobbies as lobby_api
from app.websockets.game_handlers import sio as game_sio  # Import the instance

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "*",  # For development only - remove in production
]

# Create the FastAPI app
app = FastAPI(title="Secret Hitler Backend")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create the Socket.IO ASGI app
# Important: create this BEFORE mounting to FastAPI
socket_app = socketio.ASGIApp(
    game_sio,
    socketio_path="socket.io",
    other_asgi_app=app  # Use the FastAPI app as the fallback
)

# Include API routers
app.include_router(user_api.router, prefix="/users", tags=["Users"])
app.include_router(lobby_api.router, prefix="/lobbies", tags=["Lobbies"])

@app.get("/")
async def read_root():
    return {"message": "Secret Hitler Backend is running"}

# Use the socket_app as the main application
# This is crucial - we're not mounting, but using socket_app as the main app
if __name__ == "__main__":
    uvicorn.run(
        "app.main:socket_app",  # Run the socket_app instead of app
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"]
    )
