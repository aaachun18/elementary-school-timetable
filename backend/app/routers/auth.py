from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import AdminBootstrap, UserRead
from app.services import user as user_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


REGISTER_CLOSED_MESSAGE = "系統已有帳號，新帳號請由「帳號管理」建立"


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user_data: AdminBootstrap, db: Session = Depends(get_db)) -> User:
    # Task 57 / 帳號改版: anonymous registration exists ONLY to bootstrap
    # the very first account of an empty system (nothing exists yet that
    # could authorize it), and that account is always a 系統管理員. Once
    # any account exists it is closed (403): 教學組長 and 一般老師 accounts
    # are created through POST /api/v1/users/, and no further 系統管理員
    # can be created.
    #
    # The emptiness check and the insert share one transaction, under a
    # table lock -- see lock_users_and_check_empty().
    if user_service.lock_users_and_check_empty(db):
        return user_service.create_bootstrap_admin(db, user_data.username, user_data.password)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=REGISTER_CLOSED_MESSAGE)


@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Token:
    # 帳號 of 教學組長 / 一般老師 is their (lower case) email; the
    # 系統管理員's is matched as typed.
    typed = form_data.username.strip()
    user = user_service.get_user_by_username(db, typed) or user_service.get_user_by_username(
        db, typed.lower()
    )
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
    # write endpoint still independently enforces role via require_admin / require_manager
    # (app/core/dependencies.py) regardless of what a client-decoded token
    # claims.
    access_token = create_access_token({"sub": user.username, "role": user.role})
    return Token(access_token=access_token)


@router.post("/refresh", response_model=Token)
def refresh(current_user: User = Depends(get_current_user)) -> Token:
    """Idle logout: a new token, with a fresh expiry, for someone still
    working -- the frontend asks for one while they are active, so only
    someone idle for IDLE_TIMEOUT_MINUTES is logged out. Needs a valid
    (unexpired) token of an active account, like any other call; the role
    is read again from the account, not copied from the old token."""
    access_token = create_access_token(
        {"sub": current_user.username, "role": current_user.role}
    )
    return Token(access_token=access_token)
