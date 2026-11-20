import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pymongo import DESCENDING
import uvicorn

from config import settings
from database import close_database_connection, connect_to_database, get_projects_collection
from deps import get_current_user
from serializers import serialize_project, serialize_project_summary

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [ProjectService]: %(message)s")
logger = logging.getLogger("project_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_database()
    yield
    await close_database_connection()


app = FastAPI(title="NxtBuild Projects Microservice", version="1.0.0", lifespan=lifespan)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "message": str(exc.detail)})


def parse_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project ID format.")


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "project-service"}


@app.get("/projects")
async def get_projects(current_user: dict = Depends(get_current_user)):
    user_oid = ObjectId(current_user["id"])
    projects_coll = get_projects_collection()
    cursor = projects_coll.find(
        {"user": user_oid},
        projection={"title": 1, "code": 1, "updatedAt": 1}
    ).sort("updatedAt", DESCENDING)

    projects = await cursor.to_list(length=500)
    return {"success": True, "projects": [serialize_project_summary(p) for p in projects]}


@app.post("/projects", status_code=status.HTTP_201_CREATED)
async def create_project(payload: dict = None, current_user: dict = Depends(get_current_user)):
    payload = payload or {}
    raw_title = payload.get("title")
    title = str(raw_title).strip()[:80] if raw_title else "Untitled project"

    now = datetime.now(timezone.utc)
    new_doc = {
        "user": ObjectId(current_user["id"]),
        "title": title or "Untitled project",
        "code": "",
        "messages": [],
        "createdAt": now,
        "updatedAt": now
    }

    projects_coll = get_projects_collection()
    result = await projects_coll.insert_one(new_doc)
    new_doc["_id"] = result.inserted_id

    return {"success": True, "project": serialize_project(new_doc)}


@app.get("/projects/{id}")
async def get_project(id: str, current_user: dict = Depends(get_current_user)):
    project_oid = parse_object_id(id)
    user_oid = ObjectId(current_user["id"])
    projects_coll = get_projects_collection()

    project = await projects_coll.find_one({"_id": project_oid, "user": user_oid})
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    return {"success": True, "project": serialize_project(project)}


@app.put("/projects/{id}")
async def update_project(id: str, payload: dict = None, current_user: dict = Depends(get_current_user)):
    project_oid = parse_object_id(id)
    user_oid = ObjectId(current_user["id"])
    payload = payload or {}
    projects_coll = get_projects_collection()

    project = await projects_coll.find_one({"_id": project_oid, "user": user_oid})
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    update_fields = {"updatedAt": datetime.now(timezone.utc)}

    if "title" in payload and isinstance(payload["title"], str):
        clean_title = payload["title"].strip()
        update_fields["title"] = clean_title[:80] if clean_title else "Untitled project"

    if "code" in payload and isinstance(payload["code"], str):
        update_fields["code"] = payload["code"]

    await projects_coll.update_one({"_id": project_oid}, {"$set": update_fields})
    project.update(update_fields)

    return {"success": True, "project": serialize_project(project)}


@app.delete("/projects/{id}")
async def delete_project(id: str, current_user: dict = Depends(get_current_user)):
    project_oid = parse_object_id(id)
    user_oid = ObjectId(current_user["id"])
    projects_coll = get_projects_collection()

    result = await projects_coll.delete_one({"_id": project_oid, "user": user_oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    return {"success": True, "message": "Project deleted."}


# --- Internal Service-to-Service Endpoints (used by AI Service) ---

@app.get("/internal/projects/{id}")
async def get_project_internal(id: str, user_id: str):
    """Internal endpoint for AI Service to retrieve project code & history."""
    project_oid = parse_object_id(id)
    user_oid = parse_object_id(user_id)
    projects_coll = get_projects_collection()

    project = await projects_coll.find_one({"_id": project_oid, "user": user_oid})
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    return {"success": True, "project": serialize_project(project)}


@app.put("/internal/projects/{id}/generated-code")
async def save_generated_code_internal(id: str, payload: dict):
    """Internal endpoint for AI Service to commit generated HTML and chat turns."""
    project_oid = parse_object_id(id)
    user_id = payload.get("user_id")
    user_oid = parse_object_id(user_id)
    code = payload.get("code", "")
    prompt = payload.get("prompt", "")
    summary = payload.get("summary", "")
    title = payload.get("title")

    projects_coll = get_projects_collection()
    project = await projects_coll.find_one({"_id": project_oid, "user": user_oid})
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    now = datetime.now(timezone.utc)
    user_msg = {"_id": ObjectId(), "role": "user", "text": prompt, "createdAt": now}
    ai_msg = {"_id": ObjectId(), "role": "ai", "text": summary, "createdAt": now}

    existing_messages = project.get("messages", [])
    updated_messages = list(existing_messages) + [user_msg, ai_msg]

    update_data = {
        "code": code,
        "messages": updated_messages,
        "updatedAt": now
    }

    if project.get("title") == "Untitled project" and title:
        update_data["title"] = str(title)[:80]

    await projects_coll.update_one({"_id": project_oid}, {"$set": update_data})
    project.update(update_data)

    return {"success": True, "project": serialize_project(project)}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=False)
