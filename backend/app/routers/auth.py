from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserRead
from app.services import user as user_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)) -> User:
    # Deliberately no auth dependency here: bootstrapping the very first
    # ADMIN account has no existing account that could authorize it.
    # Locking down who may register is a later Task, not this one.
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
