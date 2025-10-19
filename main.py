import re
from ipaddress import ip_address
from typing import Callable
from pathlib import Path

import redis.asyncio as redis
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi_limiter import FastAPILimiter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


from src.database.db import get_db
from src.routers import contact, auth, users
from src.conf.config import config

app = FastAPI()
banned_ips = [
    ip_address("192.168.1.1"),
    ip_address("192.168.1.2"),
    ip_address("127.0.0.1"),
]
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


user_agent_ban_list = [r"Googlebot", r"Python-urllib"]


@app.middleware("http")
async def user_agent_ban_middleware(request: Request, call_next: Callable):
    """
    Middleware to block requests from banned user-agents.
    
    Args:
        request (Request): Incoming HTTP request.
        call_next (Callable): Function to process the request.
    
    Returns:
        Response or JSONResponse with 403 status if banned user-agent detected.
    """
    print(request.headers.get("Authorization"))
    user_agent = request.headers.get("user-agent")
    print(user_agent)
    for ban_pattern in user_agent_ban_list:
        if re.search(ban_pattern, user_agent): # type: ignore
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "You are banned"},
            )
    response = await call_next(request)
    return response


# BASE_DIR = Path(".")
BASE_DIR = Path(__file__).parent


app.mount("/static", StaticFiles(directory=BASE_DIR/"src"/"static"), name="static")


app.include_router(contact.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(auth.router, prefix="/auth")




@app.on_event("startup")
async def startup():
    """
    Startup event handler to initialize Redis connection and FastAPI rate limiter.
    """
    r = await redis.Redis(
        host=config.REDIS_DOMAIN,
        port=config.REDIS_PORT,
        db=0,
        password=config.REDIS_PASSWORD,
    )
    await FastAPILimiter.init(r)


templates = Jinja2Templates(directory=BASE_DIR / "src" / "templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """
    Serve the homepage with a simple template rendering.
    """
    return templates.TemplateResponse('index.html', {"request": request, "our": "Build group WebPython"})


@app.get("/api/healthchecker")
async def healthchecker(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint to verify database connectivity.

    Returns:
        JSON message confirming service health.
    Raises:
        HTTPException if database is not configured or unreachable.
    """
    try:
        # Make request
        result = await db.execute(text("SELECT 1"))
        result = result.fetchone()
        if result is None:
            raise HTTPException(status_code=500, detail="Database is not configured correctly")
        return {"message": "Welcome to FastAPI!"}
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Error connecting to the database")
