from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def check_health():
    return {"status": "healthy"}
