from sqlalchemy.future import select
from sqlalchemy import or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from src.entity.models import Contact
from src.schemas.contact import ContactUpdate, ContactSchema
from datetime import date, timedelta



from sqlalchemy import or_

async def create_contact(body: ContactSchema, db: AsyncSession, user_id: int):
    """
    Creates a new contact for the specified user.

    :param body: The contact data.
    :type body: ContactSchema
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :param user_id: The ID of the user creating the contact.
    :type user_id: int
    :raises ValueError: If a contact with the same email or phone already exists.
    :return: The created contact.
    :rtype: Contact
    """
    stmt = select(Contact).filter(
        Contact.user_id == user_id,
        or_(
            Contact.email == body.email,
            Contact.phone == body.phone
        )
    )
    existing = await db.execute(stmt)
    if existing.scalar_one_or_none():
        raise ValueError("Contact with this email or phone already exists")

    contact = Contact(**body.model_dump(exclude_unset=True), user_id=user_id)
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


async def get_all_contacts(limit: int, offset: int, db: AsyncSession, user_id: int):
    """
    Retrieves a paginated list of all contacts for a specific user.

    :param limit: The maximum number of contacts to retrieve.
    :type limit: int
    :param offset: The number of contacts to skip.
    :type offset: int
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :param user_id: The ID of the user whose contacts are being retrieved.
    :type user_id: int
    :return: A list of contacts.
    :rtype: List[Contact]
    """
    stmt = select(Contact).filter_by(user_id=user_id).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()



async def get_contact(contact_id: int, db: AsyncSession, user_id: int):
    """
    Retrieves a specific contact by its ID for a given user.

    :param contact_id: The ID of the contact.
    :type contact_id: int
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :param user_id: The ID of the user.
    :type user_id: int
    :return: The contact if found, else None.
    :rtype: Contact | None
    """
    stmt = select(Contact).filter_by(id=contact_id, user_id=user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()



async def update_contact(contact_id: int, body: ContactUpdate, db: AsyncSession, user_id: int):
    """
    Updates an existing contact's details.

    :param contact_id: The ID of the contact to update.
    :type contact_id: int
    :param body: The updated contact data.
    :type body: ContactUpdate
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :param user_id: The ID of the user who owns the contact.
    :type user_id: int
    :raises ValueError: If another contact with the same email or phone exists.
    :return: The updated contact, or None if not found.
    :rtype: Contact | None
    """
    stmt = select(Contact).filter_by(id=contact_id, user_id=user_id)
    result = await db.execute(stmt)
    contact = result.scalar_one_or_none()

    if contact is None:
        return None

    conditions = []
    if body.email:
        conditions.append(Contact.email == body.email)
    if body.phone:
        conditions.append(Contact.phone == body.phone)

    if conditions:
        stmt = select(Contact).filter(
            Contact.user_id == user_id,
            or_(*conditions),
            Contact.id != contact_id
        )
        existing = await db.execute(stmt)
        if existing.scalar_one_or_none():
            raise ValueError("Another contact with this email or phone already exists")

    if body.first_name is not None:
        contact.first_name = body.first_name
    if body.last_name is not None:
        contact.last_name = body.last_name
    if body.email is not None:
        contact.email = body.email
    if body.phone is not None:
        contact.phone = body.phone
    if body.birthday is not None:
        contact.birthday = body.birthday
    if body.extra_info is not None:
        contact.extra_info = body.extra_info

    await db.commit()
    await db.refresh(contact)

    return contact




async def delete_contact(contact_id: int, db: AsyncSession, user_id: int):
    """
    Deletes a contact by its ID for a given user.

    :param contact_id: The ID of the contact to delete.
    :type contact_id: int
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :param user_id: The ID of the user who owns the contact.
    :type user_id: int
    :return: The deleted contact if found and deleted, else None.
    :rtype: Contact | None
    """
    stmt = select(Contact).filter_by(id=contact_id, user_id=user_id)
    contact = await db.execute(stmt)
    contact = contact.scalar_one_or_none()
    if contact:
        await db.delete(contact)
        await db.commit()
    return contact



async def search_contacts(query: str, db: AsyncSession, user_id: int):
    """
    Searches for contacts by first name, last name, or email.

    :param query: The search string.
    :type query: str
    :param db: The asynchronous database session.
    :type db: AsyncSession
    :param user_id: The ID of the user whose contacts are searched.
    :type user_id: int
    :return: A list of matching contacts.
    :rtype: List[Contact]
    """
    result = await db.execute(
        select(Contact).filter(
            Contact.user_id == user_id,
            or_(
                Contact.first_name.ilike(f"%{query}%"),
                Contact.last_name.ilike(f"%{query}%"),
                Contact.email.ilike(f"%{query}%"),
            )
        )
    )
    return result.scalars().all()



async def upcoming_birthdays(db: AsyncSession, user_id: int):
    """
    Retrieves contacts with birthdays in the next 7 days.

    :param db: The asynchronous database session.
    :type db: AsyncSession
    :param user_id: The ID of the user.
    :type user_id: int
    :return: A list of contacts with upcoming birthdays.
    :rtype: List[Contact]
    """
    today = date.today()
    next_week = today + timedelta(days=7)
    result = await db.execute(
        select(Contact).filter(
            Contact.user_id == user_id,
            Contact.birthday.between(today, next_week)
        )
    )
    return result.scalars().all()
