import os
from pathlib import Path

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors
from pydantic import EmailStr

from src.services.auth import auth_service
from src.conf.config import config


conf = ConnectionConfig(
    MAIL_USERNAME = config.MAIL_USERNAME,
    MAIL_PASSWORD = config.MAIL_PASSWORD, # type: ignore
    MAIL_FROM = config.MAIL_FROM,
    MAIL_PORT = config.MAIL_PORT,
    MAIL_SERVER = config.MAIL_SERVER,
    MAIL_FROM_NAME="TODO Systems",
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
    TEMPLATE_FOLDER=Path(__file__).parent / 'templates',
)


async def send_email(email: EmailStr, username: str, host: str):
    """
    Send an email with a verification token using a predefined HTML template.

    Args:
        email (EmailStr): Recipient's email address.
        username (str): Recipient's username for personalization.
        host (str): Base URL of the application to build verification link.

    Raises:
        ConnectionErrors: If there is an error connecting to the email server.
    """
    try:
        token_verification = auth_service.create_email_token({"sub": email})
        message = MessageSchema(
            subject="Confirm your email ",
            recipients=[email],
            template_body={"host": host, "username": username, "token": token_verification},
            subtype=MessageType.html
        )

        fm = FastMail(conf)
        await fm.send_message(message, template_name="verify_email.html")
    except ConnectionErrors as err:
        print(err)
