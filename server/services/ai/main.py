import logging
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
import httpx
import uvicorn

from concurrency import concurrency_manager
from config import settings
from deps import get_current_user
from gemini import generate_page

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [AIService]: %(message)s")
logger = logging.getLogger("ai_service")

app = FastAPI(title="NxtBuild AI Generation Microservice", version="1.0.0")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "message": str(exc.detail)})


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "ai-service"}


@app.post("/generate/{project_id}")
async def generate(project_id: str, payload: dict = None, current_user: dict = Depends(get_current_user)):
    payload = payload or {}
    prompt = payload.get("prompt")

    if not prompt or not isinstance(prompt, str) or not prompt.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Describe what you want to build or change first.")

    clean_prompt = prompt.strip()
    if len(clean_prompt) > 2000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="That prompt is too long. Keep it under 2000 characters.")

    # Concurrency guard per project ID
    lock_acquired = await concurrency_manager.acquire(project_id)
    if not lock_acquired:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A build is already in progress for this project. Please wait a moment."
        )

    user_id = current_user["id"]
    project_url = f"{settings.PROJECT_SERVICE_URL.rstrip('/')}/internal/projects/{project_id}?user_id={user_id}"

    try:
        # 1. Fetch current project state from Project Service
        async with httpx.AsyncClient(timeout=10.0) as client:
            proj_resp = await client.get(project_url)
            if proj_resp.status_code != 200:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
            project = proj_resp.json()["project"]

        # 2. Call Google Gemini via AI service
        existing_messages = project.get("messages", [])
        recent_history = existing_messages[-6:]

        result = await generate_page(
            prompt=clean_prompt,
            current_code=project.get("code", ""),
            history=recent_history
        )

        # 3. Save generated code & chat messages back to Project Service
        save_url = f"{settings.PROJECT_SERVICE_URL.rstrip('/')}/internal/projects/{project_id}/generated-code"
        commit_payload = {
            "user_id": user_id,
            "code": result["html"],
            "prompt": clean_prompt,
            "summary": result["summary"],
            "title": result.get("title")
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            save_resp = await client.put(save_url, json=commit_payload)
            if save_resp.status_code != 200:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to save generated page.")
            updated_project = save_resp.json()["project"]

        return {"success": True, "project": updated_project}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Generation error on project {project_id}: {exc}")
        err_str = str(exc).lower()
        if "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="The AI is busy right now. Wait a minute and try again.")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="The AI could not build that. Try again, or word the request a little differently.")
    finally:
        await concurrency_manager.release(project_id)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=False)
