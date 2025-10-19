import pickle

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, HTTPException, Depends, status, Path, Query, UploadFile, File
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.db import get_db
from src.crud import contact as crud
from src.schemas.contact import UserRead
from src.entity.models import User, Role 
from src.routers.auth import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from src.services.auth import auth_service
from src.services.roles import RoleAccess
from src.conf.config import config
from src.crud.users import update_avatar_url



router = APIRouter(prefix="/users", tags=["users"])
cloudinary.config(
    cloud_name=config.CLD_NAME,
    api_key=config.CLD_API_KEY,
    api_secret=config.CLD_API_SECRET,
    secure=True,
)


@router.get("/me", response_model=UserRead, dependencies=[Depends(RateLimiter(times=1, seconds=20))])
async def get_current_user(current_user: User = Depends(auth_service.get_current_user)): # type: ignore
    """
    Get the currently authenticated user's profile.

    :param current_user: The user extracted from the access token.
    :type current_user: User
    :return: The current user's profile information.
    :rtype: UserRead
    """
    return current_user


@router.patch("/avatar", response_model=UserRead, dependencies=[Depends(RateLimiter(times=1, seconds=20))])
async def get_current_user(file: UploadFile=File(), current_user: User = Depends(auth_service.get_current_user),
                            db: AsyncSession=Depends(get_db)):
    """
    Uploads and updates the current user's avatar using Cloudinary.

    The uploaded image is resized to 250x250 pixels and stored under a path
    based on the user's email. After updating the avatar URL in the database,
    the user data is cached in Redis for quick retrieval.

    :param file: The image file to upload.
    :type file: UploadFile
    :param current_user: The authenticated user.
    :type current_user: User
    :param db: Async database session.
    :type db: AsyncSession
    :return: The updated user profile.
    :rtype: UserRead
    """
    public_id = f"Web16/{current_user.email}"
    file.file.seek(0)
    res = cloudinary.uploader.upload(file.file, public_id=public_id, overwrite=True)
    print(res)
    res_url = cloudinary.CloudinaryImage(public_id).build_url(width=250, height=250, crop='fill', version=res.get('version'))

    user = await update_avatar_url(current_user.email, res_url, db)
    auth_service.cache.set(user.email, pickle.dumps(user))
    auth_service.cache.expire(user.email, 300)

    return current_user