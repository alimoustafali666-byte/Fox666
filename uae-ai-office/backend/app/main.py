import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AppError


def create_app() -> FastAPI:
    stop_event = asyncio.Event()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        from app.modules.briefs.scheduler import scheduler_loop

        task = asyncio.create_task(scheduler_loop(stop_event))
        yield
        stop_event.set()
        await task

    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI's default handler echoes the raw submitted value back in
        # each error's "input" field -- harmless for most fields, but for
        # signup/login this would put the plaintext password straight into
        # the HTTP response body. Report only loc/msg/type; never the
        # value that was submitted.
        details = [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Invalid request.",
                    "details": details,
                }
            },
        )

    app.include_router(api_router)
    return app


app = create_app()

