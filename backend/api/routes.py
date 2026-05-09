from fastapi import APIRouter
from .patients import router as patients_router
from .vitals import router as vitals_router
from .analysis import router as analysis_router
from .demo import router as demo_router
from .mcp import router as mcp_router
from .a2a import router as a2a_router
from .websocket import router as ws_router

router = APIRouter(prefix="/api/v1")

router.include_router(patients_router, tags=["patients"])
router.include_router(vitals_router, tags=["vitals"])
router.include_router(analysis_router, tags=["analysis"])
router.include_router(demo_router, tags=["demo"])
router.include_router(mcp_router, tags=["mcp"])
router.include_router(a2a_router, tags=["a2a"])
router.include_router(ws_router, tags=["websocket"])
