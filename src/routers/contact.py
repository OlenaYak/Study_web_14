from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from src.database.db import get_db
from src.crud import contact as crud
from src.schemas.contact import ContactResponse, ContactUpdate, ContactSchema
from src.entity.models import User, Role 
from src.routers.auth import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from src.services.auth import auth_service
from src.services.roles import RoleAccess



router = APIRouter(prefix="/contacts", tags=["contacts"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

access_to_route_all = RoleAccess([Role.admin, Role.moderator])


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    """
    Extracts and validates the current user from the JWT token.

    :param token: JWT access token.
    :type token: str
    :param db: Async database session.
    :type db: AsyncSession
    :raises HTTPException: If the token is invalid or user does not exist.
    :return: Authenticated User.
    :rtype: User
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user



@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    body: ContactSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)):
    """
    Creates a new contact for the current user.

    :param body: Contact creation data.
    :type body: ContactSchema
    :param db: Async database session.
    :type db: AsyncSession
    :param current_user: Authenticated user.
    :type current_user: User
    :raises HTTPException: If contact with same email or phone already exists.
    :return: Created contact.
    :rtype: Contact
    """

    try:
        contact = await crud.create_contact(body, db, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return contact



@router.get("/", response_model=List[ContactResponse])
async def get_all_contacts(
    limit: int = Query(10, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)):
    """
    Retrieves a paginated list of contacts for the current user.

    :param limit: Number of contacts to return.
    :type limit: int
    :param offset: Number of contacts to skip.
    :type offset: int
    :param db: Async database session.
    :type db: AsyncSession
    :param current_user: Authenticated user.
    :type current_user: User
    :return: List of contacts.
    :rtype: List[Contact]
    """

    contacts = await crud.get_all_contacts(limit, offset, db, current_user.id)
    return contacts



@router.get("/{contact_id}", response_model=ContactResponse)
async def get_by_id(
    contact_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)):
    """
    Retrieves a contact by its ID for the current user.

    :param contact_id: Contact ID.
    :type contact_id: int
    :param db: Async database session.
    :type db: AsyncSession
    :param current_user: Authenticated user.
    :type current_user: User
    :raises HTTPException: If contact not found.
    :return: Contact details.
    :rtype: Contact
    """

    contact = await crud.get_contact(contact_id, db, current_user.id)
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return contact


@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    body: ContactUpdate,
    contact_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)):
    """
    Updates an existing contact's data.

    :param body: Contact update data.
    :type body: ContactUpdate
    :param contact_id: ID of the contact to update.
    :type contact_id: int
    :param db: Async database session.
    :type db: AsyncSession
    :param current_user: Authenticated user.
    :type current_user: User
    :raises HTTPException: If contact not found or duplicate email/phone.
    :return: Updated contact.
    :rtype: Contact
    """

    try:
        c_updated = await crud.update_contact(contact_id, body, db, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    if c_updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return c_updated




@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)):
    """
    Deletes a contact by ID.

    :param contact_id: ID of the contact to delete.
    :type contact_id: int
    :param db: Async database session.
    :type db: AsyncSession
    :param current_user: Authenticated user.
    :type current_user: User
    :raises HTTPException: If contact not found.
    :return: No content.
    :rtype: None
    """

    deleted = await crud.delete_contact(contact_id, db, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return None  


@router.get("/search/", response_model=List[ContactResponse])
async def search_contacts(
    query: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)):
    """
    Searches contacts by name or email.

    :param query: Search string (partial match).
    :type query: str
    :param db: Async database session.
    :type db: AsyncSession
    :param current_user: Authenticated user.
    :type current_user: User
    :return: List of matched contacts.
    :rtype: List[Contact]
    """
    results = await crud.search_contacts(query, db, current_user.id)
    return results


@router.get("/upcoming/birthdays", response_model=List[ContactResponse])
async def upcoming_birthdays(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user)):
    """
    Returns a list of contacts with birthdays in the next 7 days.

    :param db: Async database session.
    :type db: AsyncSession
    :param current_user: Authenticated user.
    :type current_user: User
    :return: List of contacts with upcoming birthdays.
    :rtype: List[Contact]
    """
    results = await crud.upcoming_birthdays(db, current_user.id)
    return results
