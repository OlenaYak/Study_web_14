from datetime import datetime, timedelta
from typing import Optional
import redis
import pickle

from fastapi import Depends, HTTPException, status
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from src.database.db import get_db
from src.crud import users as repository_users
from src.conf.config import config



class Auth:
    """
    The Auth class provides methods for user authentication,
    including password hashing, JWT token creation and validation,
    caching users in Redis, and retrieving the current user.

    Attributes:
        pwd_context (CryptContext): Password hashing context.
        SECRET_KEY (str): JWT secret key.
        ALGORITHM (str): JWT encryption algorithm.
        cache (redis.Redis): Redis connection for caching users.
        oauth2_scheme (OAuth2PasswordBearer): OAuth2 scheme to extract token from the Authorization header.
    """
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    SECRET_KEY = config.SECRET_KEY_JWT
    ALGORITHM = config.ALGORITHM
    cache = redis.Redis(
        host=config.REDIS_DOMAIN,
        port=config.REDIS_PORT,
        db=0,
        password=config.REDIS_PASSWORD,
    )

    def verify_password(self, plain_password, hashed_password):
        """
        Verify if a plain password matches the hashed password.

        :param plain_password: The plain text password.
        :param hashed_password: The hashed password.
        :return: True if passwords match, else False.
        :rtype: bool
        """
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str):
        """
        Hash the password using bcrypt.

        :param password: Plain text password.
        :return: Hashed password.
        :rtype: str
        """
        return self.pwd_context.hash(password)

    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

    # define a function to generate a new access token
    async def create_access_token(self, data: dict, expires_delta: Optional[float] = None):
        """
        Create a JWT access token with the given data and expiration.

        :param data: Data to encode in the token (e.g., {"sub": user_id}).
        :param expires_delta: Token lifetime in seconds (default 15 minutes).
        :return: Encoded JWT access token.
        :rtype: str
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + timedelta(seconds=expires_delta)
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"iat": datetime.utcnow(), "exp": expire, "scope": "access_token"})
        encoded_access_token = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_access_token

    # define a function to generate a new refresh token
    async def create_refresh_token(self, data: dict, expires_delta: Optional[float] = None):
        """
        Create a JWT refresh token with the given data and expiration.

        :param data: Data to encode in the token.
        :param expires_delta: Token lifetime in seconds (default 7 days).
        :return: Encoded JWT refresh token.
        :rtype: str
        """
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + timedelta(seconds=expires_delta)
        else:
            expire = datetime.utcnow() + timedelta(days=7)
        to_encode.update({"iat": datetime.utcnow(), "exp": expire, "scope": "refresh_token"})
        encoded_refresh_token = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_refresh_token

    async def decode_refresh_token(self, refresh_token: str):
        """
        Decode and validate the refresh token.

        :param refresh_token: JWT refresh token.
        :raises HTTPException: If the token is invalid or has an incorrect scope.
        :return: Email extracted from the token.
        :rtype: str
        """
        try:
            payload = jwt.decode(refresh_token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            if payload['scope'] == 'refresh_token':
                email = payload['sub']
                return email
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid scope for token')
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate credentials')

    async def get_current_user(self, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
        """
        Retrieve the current user based on the JWT access token.

        Uses Redis cache to speed up access.

        :param token: JWT access token (auto extracted from Authorization header).
        :param db: Async database session.
        :raises HTTPException: If token is invalid or user not found.
        :return: User object.
        :rtype: User
        """
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            # Decode JWT
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])


            if payload["scope"] == 'access_token':
                user_id = payload.get("sub") 
                if user_id is None:
                    raise credentials_exception
                # email = payload["sub"]
                # if email is None:
                #     raise credentials_exception
            else:
                raise credentials_exception
        except JWTError as e:
            raise credentials_exception

        user_hash = str(user_id) # замінла email на int(user_id)

        user = self.cache.get(user_hash)

        if user is None:
            print("User from database")
            user = await repository_users.get_user_by_email(user_id, db)  # замінла email на int(user_id)
            if user is None:
                raise credentials_exception
            self.cache.set(user_hash, pickle.dumps(user))
            self.cache.expire(user_hash, 300)
        else:
            print("User from cache")
            user = pickle.loads(user)  # type: ignore
        return user
        # user = await repository_users.get_user_by_id(int(user_id), db) # замінла email на int(user_id)
        # if user is None:
        #     raise credentials_exception
        # return user

    def create_email_token(self, data: dict):
        """
        Create a JWT email confirmation token with a 1-day expiration.

        :param data: Data to encode in the token.
        :return: Encoded JWT email confirmation token.
        :rtype: str
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=1)
        to_encode.update({"iat": datetime.utcnow(), "exp": expire})
        token = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return token

    async def get_email_from_token(self, token: str):
        """
        Decode the email confirmation token and return the email.

        :param token: JWT email confirmation token.
        :raises HTTPException: If the token is invalid.
        :return: Email extracted from the token.
        :rtype: str
        """
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            email = payload["sub"]
            return email
        except JWTError as e:
            print(e)
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail="Invalid token for email verification")


auth_service = Auth()
