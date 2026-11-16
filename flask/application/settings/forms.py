from dataclasses import dataclass
from typing import Any


@dataclass
class AccountForm:
    username: str = ""
    email: str = ""
    language: str = ""
    current_password: str = ""
    new_password: str = ""
    confirm_password: str = ""

    @classmethod
    def from_request(cls, form_data: Any) -> "AccountForm":
        return cls(
            username=str(form_data.get("username", "")).strip(),
            email=str(form_data.get("email", "")).strip().lower(),
            language=str(form_data.get("language", "")).strip(),
            current_password=str(form_data.get("current_password", "")),
            new_password=str(form_data.get("new_password", "")),
            confirm_password=str(form_data.get("confirm_password", "")),
        )
