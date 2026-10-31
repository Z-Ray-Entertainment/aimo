from datetime import datetime, timezone

from domain.auth.exceptions import AuthError
from domain.auth.models import User
from shared.utils import hash_password, verify_password


class AuthService:
    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        is_initial_admin: bool = False,
    ) -> User:
        cleaned_username = username.strip()
        cleaned_email = email.strip().lower()

        if not cleaned_username:
            raise AuthError("Username must not be empty.")
        if not cleaned_email or "@" not in cleaned_email:
            raise AuthError("A valid email address is required.")
        if not password:
            raise AuthError("Password must not be empty.")

        return User(
            id=None,
            username=cleaned_username,
            email=cleaned_email,
            password_hash=hash_password(password),
            is_initial_admin=is_initial_admin,
            created_at=datetime.now(timezone.utc),
        )

    def authenticate_user(self, user: User, password: str) -> bool:
        if not password or not user.password_hash:
            return False
        return verify_password(password, user.password_hash)

    def change_password(self, user: User, new_password: str) -> None:
        if not new_password:
            raise AuthError("New password must not be empty.")
        user.password_hash = hash_password(new_password)
