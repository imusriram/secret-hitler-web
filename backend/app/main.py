from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio  # Uncommented this import

app = FastAPI(title="Secret Hitler XL Backend")

# Configure CORS (Cross-Origin Resource Sharing)
# Allows your React frontend (running on a different port)
# to communicate with the backend.
# Adjust origins as needed for development/production.
origins = [
    "http://localhost:5173",  # Default Vite dev port
    "http://127.0.0.1:5173",
    # Add your deployed frontend URL later
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)


@app.get("/")
async def read_root():
    return {"message": "Secret Hitler XL Backend is running!"}

# Socket.IO setup
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=origins)
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)  # Wrap FastAPI app


# Add other routers later
# from app.api import users, lobbies, game
# app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
# app.include_router(lobbies.router, prefix="/api/v1/lobbies", tags=["lobbies"])
# app.include_router(game.router, prefix="/api/v1/game", tags=["game"])

# To run (without Socket.IO initially): uvicorn app.main:app --reload --port 8000
# To run (with Socket.IO): uvicorn app.main:socket_app --reload --port 8000
