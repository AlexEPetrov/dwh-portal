from api.host import app
from fastapi import Request


@app.middleware('http')
async def check_api_key(request: Request, call_next):
    # Пока без авторизации. Оставляю здесь как демо кастомного метода авторизации для FastAPI
    # if request.headers.get("Api-Key") is None and request.query_params.get("Api-Key") is None:
    #    return JSONResponse(None, 401, {"errorMessage": "Authentication failed"})
    return await call_next(request)
