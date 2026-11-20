from datetime import datetime


def serialize_message(msg: dict) -> dict:
    created = msg.get("createdAt")
    created_str = created.isoformat() if isinstance(created, datetime) else (str(created) if created else "")
    res = {
        "role": msg.get("role", "user"),
        "text": msg.get("text", ""),
        "createdAt": created_str
    }
    if "_id" in msg and msg["_id"]:
        res["_id"] = str(msg["_id"])
    return res


def serialize_project(doc: dict) -> dict:
    created = doc.get("createdAt")
    updated = doc.get("updatedAt")
    return {
        "_id": str(doc["_id"]),
        "user": str(doc.get("user", "")),
        "title": doc.get("title", "Untitled project"),
        "code": doc.get("code", ""),
        "messages": [serialize_message(m) for m in doc.get("messages", [])],
        "createdAt": created.isoformat() if isinstance(created, datetime) else (str(created) if created else ""),
        "updatedAt": updated.isoformat() if isinstance(updated, datetime) else (str(updated) if updated else "")
    }


def serialize_project_summary(doc: dict) -> dict:
    updated = doc.get("updatedAt")
    return {
        "_id": str(doc["_id"]),
        "title": doc.get("title", "Untitled project"),
        "code": doc.get("code", ""),
        "updatedAt": updated.isoformat() if isinstance(updated, datetime) else (str(updated) if updated else "")
    }
