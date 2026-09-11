import os

import uvicorn

from api.portal_host import app


if __name__ == "__main__":
    port = int(os.getenv("APP_API_PORT", "5011"))
    uvicorn.run(app, host="0.0.0.0", port=port)
