from fastapi import APIRouter, HTTPException, status, Depends, Request, BackgroundTasks, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone
from fastapi.security import OAuth2PasswordRequestForm, HTTPAuthorizationCredentials, HTTPBearer

from src.utils.security import hash_password, verify_password
from src.entity.models import User
from src.database.db import get_db
from src.schemas.user import UserCreate, UserRead, TokenRefresh, RequestEmail, TokenSchema
from src.services.auth import auth_service
from src.services.email import send_email
from src.conf.config import config


SECRET_KEY = config.SECRET_KEY_JWT
ALGORITHM = config.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7


router = APIRouter(tags=["auth"])

get_refresh_token = HTTPBearer()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def get_user_by_email(email: str, db: AsyncSession) -> User | None:
    """
    Retrieves a user by their email address.

    :param email: The user's email address.
    :type email: str
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :return: User object if found, else None.
    :rtype: User | None
    """
    stmt = select(User).filter_by(email=email)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()



async def update_token(user: User, token: str | None, db: AsyncSession) -> None:
    """
    Updates the refresh token for a user.

    :param user: The user object.
    :type user: User
    :param token: The new refresh token.
    :type token: str | None
    :param db: The asynchronous database session.
    :type db: AsyncSession
    """
    user.refresh_token = token
    await db.commit()



async def confirmed_email(email: str, db: AsyncSession) -> None:
    """
    Updates the refresh token for a user.

    :param user: The user object.
    :type user: User
    :param token: The new refresh token.
    :type token: str | None
    :param db: The asynchronous database session.
    :type db: AsyncSession
    """
    user = await get_user_by_email(email, db)
    if user:
        user.confirmed = True
        await db.commit()



def create_refresh_token(user_id: int) -> str:
    """
    Creates a new refresh token for the given user ID.

    :param user_id: The user's ID.
    :type user_id: int
    :return: Encoded refresh token.
    :rtype: str
    """
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {"sub": str(user_id), "exp": expire}
    refresh_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return refresh_token



@router.post("/signup", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate, bt: BackgroundTasks, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Registers a new user and sends a confirmation email.

    :param user_data: The user's registration data.
    :type user_data: UserCreate
    :param bt: Background tasks for sending email.
    :type bt: BackgroundTasks
    :param request: The incoming HTTP request.
    :type request: Request
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :raises HTTPException: If the email is already in use.
    :return: The newly created user.
    :rtype: User
    """
    hashed_pw = hash_password(user_data.password)

    existing_user = await get_user_by_email(user_data.email, db)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail= "Account already exists!"
        )

    new_user = User(email=user_data.email, password=hashed_pw, username=user_data.username)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    bt.add_task(send_email, new_user.email, new_user.username, str(request.base_url))

    return new_user



@router.post("/login", response_model=TokenSchema)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Authenticates a user and returns access and refresh tokens.

    :param form_data: The login form containing email and password.
    :type form_data: OAuth2PasswordRequestForm
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :raises HTTPException: If credentials are invalid.
    :return: Access and refresh tokens with type.
    :rtype: dict
    """
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.confirmed:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email not confirmed",
        )
    # access_expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # access_token = jwt.encode({"sub": str(user.id), "exp": access_expire}, SECRET_KEY, algorithm=ALGORITHM)
    access_token = await auth_service.create_access_token(
    data={"sub": str(user.id)},
    expires_delta=ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    
    refresh_token = create_refresh_token(user.id)

    # збереження refresh token в БД
    await update_token(user, refresh_token, db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.get('/refresh_token', response_model=TokenSchema)
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(get_refresh_token),
                        db: AsyncSession = Depends(get_db)):
    """
    Refreshes access and refresh tokens using a valid refresh token.

    :param credentials: The HTTP Authorization credentials.
    :type credentials: HTTPAuthorizationCredentials
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :raises HTTPException: If the refresh token is invalid or expired.
    :return: New access and refresh tokens.
    :rtype: dict
    """
    token = credentials.credentials
    email = await auth_service.decode_refresh_token(token)
    user = await get_user_by_email(email, db)

    if user is None or user.refresh_token != token:
        if user:
            await update_token(user, None, db)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    access_token = await auth_service.create_access_token(data={"sub": email})
    refresh_token = await auth_service.create_refresh_token(data={"sub": email})
    await update_token(user, refresh_token, db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }



@router.get('/confirmed_email/{token}')
async def confirm_email(token: str, db: AsyncSession = Depends(get_db)):
    """
    Confirms a user's email using the provided token.

    :param token: The confirmation token.
    :type token: str
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :raises HTTPException: If verification fails.
    :return: Confirmation message.
    :rtype: dict
    """
    email = await auth_service.get_email_from_token(token)
    user = await get_user_by_email(email, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification error")
    if user.confirmed:
        
        return {"message": "Your email is already confirmed"}
    await confirmed_email(email, db)
   
    return {"message": "Email confirmed"}



@router.post('/request_email')
async def request_email(body: RequestEmail, background_tasks: BackgroundTasks, request: Request,
                        db: AsyncSession = Depends(get_db)):
    """
    Sends a new email confirmation request.

    :param body: The email request data.
    :type body: RequestEmail
    :param background_tasks: Background tasks handler.
    :type background_tasks: BackgroundTasks
    :param request: The incoming HTTP request.
    :type request: Request
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :return: Response message.
    :rtype: dict
    """
    user = await get_user_by_email(body.email, db)
    if user and user.confirmed:
        return {"message": "Your email is already confirmed"}
    if user:
        background_tasks.add_task(send_email, user.email, user.username, str(request.base_url)) # type: ignore
    return {"message": "Check your email for confirmation."}


@router.get('/{username}')
async def track_email_open(username: str, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Tracks email open events by serving a tracking image.

    :param username: The username from the email link.
    :type username: str
    :param response: The response object.
    :type response: Response
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :return: PNG image file response.
    :rtype: FileResponse
    """
    print('--------------------------------')
    print(f'{username} зберігаємо що він відкрив email в БД')
    print('--------------------------------')
    return FileResponse("src/static/open_check.png", media_type="image/png", content_disposition_type="inline")
