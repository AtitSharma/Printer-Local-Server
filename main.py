"""Main function for running the local server API."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from config import settings
from utils import add_routes, create_application

load_dotenv()

UPLOAD_DIRECTORY = Path("media")
UPLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app):
    yield


api_router = APIRouter(tags=["base"])

app = create_application(lifespan=lifespan)
app = add_routes(app)

app.root_path = settings.root_path
app.title = settings.project_name

app.mount("/media", StaticFiles(directory=UPLOAD_DIRECTORY), name="media")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
