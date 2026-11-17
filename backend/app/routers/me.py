from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.user import OwnPasswordChange, ProfileRead, ProfileUpdate
from app.services import profile as profile_service

# 帳號改版: 個人資料維護, for every logged-in account -- including an
# 一般老師 with no school, who can still see their data and change their
# password. AccountPermissionError (403) and AccountStateError (422) are
# converted by the global handlers in main.py.
router = APIRouter(prefix="/api/v1/me", tags=["me"])


@router.get("", response_model=ProfileRead)
def read_profile(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> ProfileRead:
    return profile_service.get_profile(db, current_user)


@router.patch("", response_model=ProfileRead)
def update_profile(
    data: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProfileRead:
    return profile_service.update_name(db, current_user, data.name)


@router.patch("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    data: OwnPasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    profile_service.change_own_password(
        db, current_user, data.current_password, data.new_password
    )
