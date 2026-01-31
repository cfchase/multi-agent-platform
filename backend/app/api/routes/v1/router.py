from fastapi import APIRouter
from .utils.router import router as utils_router
from .items import router as items_router
from .users import router as users_router
from .chats import router as chats_router
from .chat_messages import router as chat_messages_router
from .flows import router as flows_router

router = APIRouter()
router.include_router(utils_router, prefix="/utils")
router.include_router(items_router)
router.include_router(users_router)
router.include_router(chats_router)
router.include_router(chat_messages_router)
router.include_router(flows_router)
