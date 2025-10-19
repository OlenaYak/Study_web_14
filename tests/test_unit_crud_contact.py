import unittest
from datetime import date
from unittest.mock import MagicMock, AsyncMock, Mock

from sqlalchemy.ext.asyncio import AsyncSession

from src.entity.models import Contact, User
from src.schemas.contact import ContactSchema, ContactUpdate
from src.crud.contact import create_contact, get_all_contacts, get_contact, update_contact, delete_contact


class TestAsyncTodo(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.user = User(id=1, username='test_user', password="qwerty", confirmed=True)
        self.session = AsyncMock(spec=AsyncSession)

 

    async def test_get_all_contacts(self):
        limit = 10
        offset = 0
        contacts = [
            Contact(id=1, first_name='Alice', last_name='Smith', email='a@example.com',
                    phone='1234567890', birthday=date(1990, 1, 1), user_id=self.user.id),
            Contact(id=2, first_name='Bob', last_name='Brown', email='b@example.com',
                    phone='0987654321', birthday=date(1992, 2, 2), user_id=self.user.id)
        ]

        # mocks for scalars and its all()
        mocked_scalars = MagicMock()
        mocked_scalars.all.return_value = contacts

        # mock for execute result
        mocked_result = MagicMock()
        mocked_result.scalars.return_value = mocked_scalars

        # mock the async execute method
        self.session.execute = AsyncMock(return_value=mocked_result)

        result = await get_all_contacts(limit, offset, self.session, self.user.id)
        self.assertEqual(result, contacts)






    async def test_get_contact(self):
        contact_id = 1 
        
        contact = Contact(
            id=contact_id,
            first_name='Alice',
            last_name='Smith',
            email='alice@example.com',
            phone='1234567890',
            birthday=date(1990, 1, 1),
            user_id=self.user.id
        )

        mocked_result = MagicMock()
        mocked_result.scalar_one_or_none.return_value = contact
        self.session.execute.return_value = mocked_result

        result = await get_contact(contact_id, self.session, self.user.id)

        self.assertEqual(result, contact)



    async def test_create_contact(self):
        body = ContactSchema(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="1234567890",
            birthday=date(1990, 1, 1),
            extra_info="Test info"
        )

        # Мок, що дублікати відсутні
        mocked_result = MagicMock()
        mocked_result.scalar_one_or_none.return_value = None
        self.session.execute.return_value = mocked_result

        # Також мок для commit і refresh
        self.session.commit = AsyncMock()
        self.session.refresh = AsyncMock()

        result = await create_contact(body, self.session, self.user.id)

        self.assertIsInstance(result, Contact)
        self.assertEqual(result.first_name, body.first_name)
        self.assertEqual(result.last_name, body.last_name)
        self.assertEqual(result.email, body.email)



    async def test_update_contact(self):
        body = ContactUpdate(
            first_name="Jane",
            last_name="Doe",
            email="jane.doe@example.com",
            phone="0987654321",
            birthday=date(1992, 2, 2),
            extra_info="Updated info"
        )

        contact_obj = Contact(
            id=1,
            first_name="Old",
            last_name="Name",
            email="old@example.com",
            phone="1111111111",
            birthday=date(1980, 1, 1),
            extra_info="Old info",
            user_id=self.user.id
        )

        # Мок для пошуку існуючого контакту (для оновлення)
        mocked_contact = MagicMock()
        mocked_contact.scalar_one_or_none.return_value = contact_obj

        # Мок для пошуку дублікату (повертаємо None, щоб не було дубліката)
        mocked_duplicate_check = MagicMock()
        mocked_duplicate_check.scalar_one_or_none.return_value = None

        # self.session.execute викликається двічі: спочатку для пошуку контакту, потім для перевірки дублікатів
        # Надаємо два послідовних значення
        self.session.execute.side_effect = [mocked_contact, mocked_duplicate_check]

        self.session.commit = AsyncMock()
        self.session.refresh = AsyncMock()

        result = await update_contact(1, body, self.session, self.user.id)

        self.assertIsInstance(result, Contact)
        self.assertEqual(result.first_name, body.first_name) # type: ignore
        self.assertEqual(result.last_name, body.last_name) # type: ignore
        self.assertEqual(result.email, body.email) # type: ignore




    async def test_delete_contact(self):
        contact_to_delete = Contact(
            id=1,
            first_name="Test",
            last_name="User",
            email="test@example.com",
            phone="123456789",
            birthday=date(1990, 1, 1),
            user_id=self.user.id
        )

        mocked_result = MagicMock()
        mocked_result.scalar_one_or_none.return_value = contact_to_delete
        self.session.execute.return_value = mocked_result

        self.session.delete = AsyncMock()
        self.session.commit = AsyncMock()

        result = await delete_contact(1, self.session, self.user.id)

        self.session.delete.assert_called_once_with(contact_to_delete)
        self.session.commit.assert_called_once()

        self.assertIsInstance(result, Contact)

