"""
Authenticated user profile endpoint.
"""

from fastapi import APIRouter, Depends

from app.core.security import UserClaims, get_current_user
from app.schemas.iam import UserMeResponse

router = APIRouter()


@router.get("/me", response_model=UserMeResponse)
def get_me(user: UserClaims = Depends(get_current_user)):
    return UserMeResponse(
        uid=user.uid,
        email=user.email,
        name=user.name,
        role=user.role,
        status=user.status,
        organizationId=user.organization_id,
    )
