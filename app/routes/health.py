from fastapi import APIRouter
from fastapi.responses import JSONResponse
from ..core import log

health_router = APIRouter()

@health_router.get("/health")
def health_check():
    log.info("Health check endpoint called")
    return JSONResponse(content={"status": "ok"})