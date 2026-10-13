from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.user import PasswordReset, UserListItem
from app.services import user as user_service

# Task 59: account management for the frontend's 帳號管理 page. Every
# endpoint here is ADMIN-only. Creating an account is deliberately NOT
# duplicated here -- it stays POST /api/v1/auth/register (Task 57).
router = APIRouter(
    prefix="/api/v1/users",
    tags=["users"],
    dependencies=[Depends(require_admin)],
)


@router.get("/", response_model=list[UserListItem])
def list_users(db: Session = Depends(get_db)) -> list[User]:
    return user_service.get_users(db)


@router.patch("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(
    user_id: int, password_data: PasswordReset, db: Session = Depends(get_db)
) -> None:
    updated = user_service.reset_password(db, user_id, password_data.password)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )


# CannotDeleteSelfError is intentionally not caught here -- the global
# exception handler in main.py converts it to 409.
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> None:
    deleted = user_service.delete_user(db, user_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
