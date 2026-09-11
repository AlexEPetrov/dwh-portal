"""Управление запросами на фоновое выполнение"""

from uuid import UUID

from api.common import RequestStatus
from fastapi import APIRouter
from shared.request_manager import RequestManager

requests_router = APIRouter(prefix="/api/requests", tags=["requests"])


@requests_router.get("/{request_id}")
def get_report_status(request_id: UUID):
    """Получение статуса фоновой операции"""
    request = RequestManager.get_request(request_id)
    if request is not None:
        return {"status": request.status.name, "message": request.message}
    return {"status": RequestStatus.UNKNOWN.name, "message": "Not found"}


@requests_router.get("/api/requests")
def get_requests():
    """Получение списка фоновых операций"""
    return RequestManager.get_requests()
