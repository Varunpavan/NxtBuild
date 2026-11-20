import logging
from fastapi import Header, HTTPException, status
import httpx
from config import settings

logger = logging.getLogger("project_service.deps")


async def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please log in to continue."
        )

    auth_url = f"{settings.AUTH_SERVICE_URL.rstrip('/')}/auth/verify"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(auth_url, headers={"Authorization": authorization})
            if resp.status_code != 200:
                data = resp.json() if resp.content else {}
                detail = data.get("message", "Your session has expired. Please log in again.")
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)

            data = resp.json()
            return data["user"]
    except httpx.RequestError as exc:
        logger.error(f"Failed to communicate with Auth Service: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth Service is temporarily unavailable."
        )
