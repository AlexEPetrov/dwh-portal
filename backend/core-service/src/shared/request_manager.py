import datetime
from contextvars import ContextVar
from typing import Dict, Optional
from uuid import UUID, uuid4

from api.common import RequestContext, RequestStatus

CORRELATION_ID_CTX_KEY = "correlation_id"
REQUEST_ID_CTX_KEY = "request_id"

correlation_id_ctx_var: ContextVar[str] = ContextVar(CORRELATION_ID_CTX_KEY, default="")
request_id_ctx_var: ContextVar[str] = ContextVar(REQUEST_ID_CTX_KEY, default="")


def get_correlation_id() -> str:
    """Возвращает correlation id (aka operation id)"""
    return correlation_id_ctx_var.get()


def get_request_id() -> str:
    """Возвращает request id запроса на долговременный"""
    return request_id_ctx_var.get()


class RequestManager:
    """
    Класс для отслеживания состояния запросов, в т.ч. фоновых
    """

    __requests: Dict[UUID, RequestContext] = {}
    __MAX_DAILY_REQUEST_COUNT: int = 1000  # per day

    @classmethod
    def compact(cls):
        for k, v in list(cls.__requests.items()):
            if v.request_time + datetime.timedelta(hours=24) < datetime.datetime.now():
                del cls.__requests[k]

    # @classmethod
    # def create_request_id(cls) -> str:
    #     request_id = uuid4()
    #     return str(request_id)

    @classmethod
    def create_request_context(
        cls,
        request_id: Optional[UUID] = None,
        message: str = "",
    ) -> RequestContext:

        RequestManager.compact()

        if len(cls.__requests) > RequestManager.__MAX_DAILY_REQUEST_COUNT:
            raise SystemError("Превышен лимит на запросы.")

        active_request_id = get_request_id()
        if active_request_id:
            return RequestManager.get_request(UUID(active_request_id))
        else:
            effective_request_id = request_id if request_id else uuid4()
            token = request_id_ctx_var.set(str(effective_request_id))
            ret_val = RequestContext(
                request_id=effective_request_id,
                request_time=datetime.datetime.now(),
                status=RequestStatus.REQUESTED,
                message=message,
                token=token,
            )

            RequestManager.__requests[ret_val.request_id] = ret_val
            return ret_val

    @classmethod
    def get_request_status(cls, request_id: UUID) -> RequestStatus:
        context: RequestContext = RequestManager.__requests.get(
            request_id
        )  # pyright: ignore[reportAssignmentType]
        if context is not None:
            return context.status

        return RequestStatus.UNKNOWN

    @classmethod
    def get_request(cls, request_id: UUID) -> RequestContext:
        return RequestManager.__requests.get(
            request_id
        )  # pyright: ignore[reportReturnType, reportAssignmentType]

    @classmethod
    def get_requests(cls):
        return [
            {"request_id": x.request_id, "status": x.status, "message": x.message}
            for x in RequestManager.__requests.values()
        ]

    @classmethod
    def update_request_status(
        cls, request_id: UUID, status: RequestStatus, message: str = ""
    ) -> RequestStatus:
        context: RequestContext = RequestManager.__requests.get(
            request_id
        )  # pyright: ignore[reportAssignmentType]
        if context is not None:
            context.status = status
            context.message = message
            return context.status

        raise FileNotFoundError
