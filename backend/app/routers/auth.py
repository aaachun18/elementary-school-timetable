from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.dependencies import (
    get_current_user,
    optional_oauth2_scheme,
    require_admin,
)
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserRead
from app.services import user as user_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    user_data: UserCreate,
    token: str | None = Depends(optional_oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    # Task 57: anonymous registration is allowed ONLY to bootstrap the very
    # first account (nothing exists yet that could authorize it), and that
    # account is always ADMIN regardless of the requested role. Once any
    # user exists, this behaves exactly like every other write endpoint:
    # no token -> 401, non-ADMIN token -> 403 (same get_current_user /
    # require_admin logic, called directly instead of via Depends because
    # whether they apply depends on the emptiness check below).
    #
    # The emptiness check and the insert share one transaction, under a
    # table lock -- see lock_users_and_check_empty().
    if user_service.lock_users_and_check_empty(db):
        return user_service.create_user(
            db, user_data.model_copy(update={"role": "ADMIN"})
        )

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    require_admin(get_current_user(token, db))
    return user_service.create_user(db, user_data)


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Token:
    user = user_service.get_user_by_username(db, form_data.username)
    if (
        user is None
        or not user.is_active
        or not verify_password(form_data.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Phase B (Task 42): `role` is now embedded in the token itself, not
    # just looked up server-side on every request -- the frontend has no
    # other way to know the logged-in user's role (there is no GET /me
    # endpoint), and needs it to decide whether to show the
    # create/edit/delete buttons at all (see DataBrowser.tsx). This is a
    # UI convenience only, never an authorization decision by itself: every
    # write endpoint still independently enforces role via require_admin
    # (app/core/dependencies.py) regardless of what a client-decoded token
    # claims.
    access_token = create_access_token({"sub": user.username, "role": user.role})
    return Token(access_token=access_token)
