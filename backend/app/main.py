from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import agents, auth, health


app = FastAPI(title="QuickDesk API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(agents.router)

