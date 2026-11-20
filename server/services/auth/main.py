import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
import jwt
import uvicorn

from config import settings
from database import close_database_connection, connect_to_database, get_users_collection
from security import create_access_token, decode_access_token, hash_password, verify_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [AuthService]: %(message)s")
logger = logging.getLogger("auth_service")

EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_database()
    yield
    await close_database_connection()


app = FastAPI(title="NxtBuild Auth Microservice", version="1.0.0", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "message": str(exc.detail)})


async def get_authenticated_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Please log in to continue.")

    token = authorization.split(" ")[1].strip()
    try:
        payload = decode_access_token(token)
        user_id_str = payload.get("id")
        if not user_id_str:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has expired. Please log in again.")
        user_id = ObjectId(user_id_str)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your session has expired. Please log in again.")

    users = get_users_collection()
    user = await users.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This account no longer exists.")
    return user


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "auth-service"}


@app.post("/auth/signup", status_code=status.HTTP_201_CREATED)
async def signup(payload: dict):
    name = payload.get("name")
    email = payload.get("email")
    password = payload.get("password")

    if not name or not email or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Name, email and password are all required.")

    clean_email = str(email).strip().lower()
    if not EMAIL_REGEX.match(clean_email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please enter a valid email address.")

    if len(str(password)) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password needs at least 6 characters.")

    users = get_users_collection()
    existing = await users.find_one({"email": clean_email})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists. Try logging in.")

    now = datetime.now(timezone.utc)
    new_user = {
        "name": str(name).strip()[:50],
        "email": clean_email,
        "password": hash_password(str(password)),
        "createdAt": now,
        "updatedAt": now
    }

    result = await users.insert_one(new_user)
    user_id = str(result.inserted_id)

    return {
        "success": True,
        "token": create_access_token(user_id),
        "user": {"id": user_id, "name": new_user["name"], "email": new_user["email"]}
    }


@app.post("/auth/login")
async def login(payload: dict):
    email = payload.get("email")
    password = payload.get("password")

    if not email or not password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please enter your email and password.")

    clean_email = str(email).strip().lower()
    users = get_users_collection()
    user = await users.find_one({"email": clean_email})

    invalid_msg = "Email or password is incorrect."
    if not user or not verify_password(str(password), user.get("password", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=invalid_msg)

    user_id = str(user["_id"])
    return {
        "success": True,
        "token": create_access_token(user_id),
        "user": {"id": user_id, "name": user["name"], "email": user["email"]}
    }


@app.get("/auth/me")
async def me(authorization: str = Header(None)):
    user = await get_authenticated_user(authorization)
    return {
        "success": True,
        "user": {"id": str(user["_id"]), "name": user["name"], "email": user["email"]}
    }


@app.get("/auth/verify")
async def verify(authorization: str = Header(None)):
    """Internal verification endpoint used by other microservices."""
    user = await get_authenticated_user(authorization)
    return {
        "valid": True,
        "user": {"id": str(user["_id"]), "name": user["name"], "email": user["email"]}
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=False)
