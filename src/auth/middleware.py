from datetime import timedelta

from fastapi import APIRouter, BaseHTTPMiddleware, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from nicegui import app, ui

from src.auth.jwt import create_access_token, decode_access_token
from src.auth.passwords import verify_password
from src.config import get_settings
from src.db.engine import async_session
from src.db.models import User

PUBLIC_PATHS = {"/login", "/_nicegui", "/api/auth/login", "/api/auth/logout", "/api/auth/register"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path.startswith("/_nicegui") or path in PUBLIC_PATHS:
            return await call_next(request)

        token = request.cookies.get("access_token")
        if not token:
            return self._deny(request)

        settings = get_settings()
        payload = decode_access_token(
            token,
            settings.auth.jwt_secret.get_secret_value(),
            settings.auth.jwt_algorithm,
        )
        if payload is None:
            return self._deny(request)

        user_id_str = payload.get("sub")
        if user_id_str is None:
            return self._deny(request)

        request.state.user_id = user_id_str
        request.state.user_id_int = int(user_id_str)

        try:
            async with async_session() as session:
                user = await session.get(User, request.state.user_id_int)
                if user is None:
                    return self._deny(request)

                try:
                    client = app.storage.user
                    client["user_id"] = user.id
                    client["username"] = user.username
                    client["is_admin"] = user.is_admin
                except (KeyError, RuntimeError):
                    pass
        except Exception:
            return self._deny(request)

        return await call_next(request)

    @staticmethod
    def _deny(request: Request) -> Response:
        path = request.url.path
        if path.startswith("/api/"):
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
        return RedirectResponse(
            url=f"/login?redirect_to={path}",
            status_code=302,
        )


router = APIRouter(prefix="/api/auth")


@router.post("/login")
async def login(request: Request, response: Response):
    body = await request.json()
    username = body.get("username", "")
    password = body.get("password", "")

    async with async_session() as session:
        from sqlalchemy import select

        stmt = select(User).where(User.username == username)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.hashed_password):
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})

    settings = get_settings()
    token = create_access_token(
        user_id=user.id,
        secret=settings.auth.jwt_secret.get_secret_value(),
        algorithm=settings.auth.jwt_algorithm,
        expires_delta=timedelta(minutes=settings.auth.jwt_expire_minutes),
    )

    response = JSONResponse(
        content={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin,
        }
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=not get_settings().debug,
        max_age=settings.auth.jwt_expire_minutes * 60,
        path="/",
    )
    return response


@router.post("/logout")
async def logout(response: Response):
    response = JSONResponse(content={"detail": "Logged out"})
    response.delete_cookie(key="access_token", path="/")
    return response


@router.post("/register")
async def register(request: Request, response: Response):
    body = await request.json()
    username = body.get("username", "")
    email = body.get("email", "")
    password = body.get("password", "")

    if not username or not password:
        return JSONResponse(status_code=400, content={"detail": "Username and password required"})

    from src.auth.passwords import hash_password

    hashed = hash_password(password)

    async with async_session() as session:
        from sqlalchemy import select

        existing = await session.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none() is not None:
            return JSONResponse(status_code=409, content={"detail": "Username already exists"})

        user = User(username=username, email=email, hashed_password=hashed, is_admin=False)
        session.add(user)
        await session.commit()
        await session.refresh(user)

    return JSONResponse(
        status_code=201,
        content={
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
    )
