from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.models import User
from app.providers.factory import get_storage_provider

router = APIRouter(tags=["storage"])
settings = get_settings()


@router.get("/storage/{file_path:path}")
async def get_storage_file(file_path: str, user: User = Depends(get_current_user)):
    storage = get_storage_provider()
    path = await storage.open_path(file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    # Ensure path is under storage root
    root = Path(settings.storage_root).resolve()
    if not str(path.resolve()).startswith(str(root)):
        raise HTTPException(status_code=403, detail="Forbidden")
    return FileResponse(path)
