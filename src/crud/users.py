from fastapi import Depends, HTTPException
from starlette.status import HTTP_404_NOT_FOUND
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from libgravatar import Gravatar

from src.database.db import get_db
from src.entity.models import User
from src.schemas.user import UserCreate


async def get_user_by_email(email: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieves a user from the database by email.

    :param email: The email address of the user.
    :type email: str
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :return: The user object if found, otherwise None.
    :rtype: User | None
    """
    stmt = select(User).filter_by(email=email)
    user = await db.execute(stmt)
    user = user.scalar_one_or_none()
    return user



async def get_user_by_id(user_id: int, db: AsyncSession) -> User | None:
    """
    Retrieves a user from the database by their ID.

    :param user_id: The ID of the user.
    :type user_id: int
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :return: The user object if found, otherwise None.
    :rtype: User | None
    """
    stmt = select(User).filter_by(id=user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()



async def create_user(body: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Creates a new user in the database, including a Gravatar avatar.

    :param body: The user registration data.
    :type body: UserCreate
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :return: The newly created user object.
    :rtype: User
    """
    avatar = None
    try:
        g = Gravatar(body.email)
        avatar = g.get_image()
    except Exception as err:
        print(err)

    new_user = User(**body.model_dump(), avatar=avatar)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


async def update_token(user: User, token: str | None, db: AsyncSession):
    """
    Updates the refresh token for a user.

    :param user: The user object.
    :type user: User
    :param token: The new refresh token.
    :type token: str | None
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :return: None
    :rtype: None
    """
    user.refresh_token = token
    await db.commit()



async def confirmed_email(email: str, db: AsyncSession) -> None:
    """
    Marks a user's email as confirmed.

    :param email: The user's email address.
    :type email: str
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :raises HTTPException: If the user is not found.
    :return: None
    :rtype: None
    """
    user = await get_user_by_email(email, db)
    if user is None:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="User not found")
    user.confirmed = True
    await db.commit()



async def update_avatar_url(email: str, url: str|None, db: AsyncSession) -> User:
    """
    Updates the avatar URL for a user.

    :param email: The user's email address.
    :type email: str
    :param url: The new avatar URL.
    :type url: str | None
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :return: The updated user object.
    :rtype: User
    """
    user = await get_user_by_email(email, db)
    user.avatar = url # type: ignore
    await db.commit()
    return user # type: ignore