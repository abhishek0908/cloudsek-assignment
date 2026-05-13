from fastapi import APIRouter

router = APIRouter()


@router.get("/metadata")
async def get_metadata():
    return {"message": "metadata endpoint"}
