from datetime import datetime, timezone

from domain.auth.exceptions import AuthError
from domain.auth.models import User
from domain.translation.models import Language
from shared.utils import hash_password, verify_password

_DUMMY_PASSWORD_HASH: str = hash_password("aimo-constant-time-dummy-password")


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

    def authenticate_with_lookup(self, user: User | None, password: str) -> bool:
        """Constant-cost verification so unknown emails never skip bcrypt work."""
        if user is None or not user.password_hash:
            verify_password(password or "dummy", _DUMMY_PASSWORD_HASH)
            return False
        if not password:
            verify_password("dummy", _DUMMY_PASSWORD_HASH)
            return False
        return verify_password(password, user.password_hash)

    def update_name(self, user: User, username: str) -> None:
        cleaned = username.strip()
        if not cleaned:
            raise AuthError("Username must not be empty.")
        user.username = cleaned

    def update_email(self, user: User, email: str) -> None:
        cleaned = email.strip().lower()
        if not cleaned or "@" not in cleaned:
            raise AuthError("A valid email address is required.")
        user.email = cleaned

    def change_password_verified(self, user: User, current_password: str, new_password: str) -> None:
        if not self.authenticate_user(user, current_password):
            raise AuthError("Current password is incorrect.")
        self.change_password(user, new_password)

    def assign_language(self, user: User, raw_language: str) -> None:
        user.language = Language.resolve(raw_language).value

    def set_ember_particles_enabled(self, user: User, enabled: bool) -> None:
        user.ember_particles_enabled = bool(enabled)

    def change_password(self, user: User, new_password: str) -> None:
        if not new_password:
            raise AuthError("New password must not be empty.")
        user.password_hash = hash_password(new_password)
