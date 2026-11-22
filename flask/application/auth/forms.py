from dataclasses import dataclass


@dataclass
class LoginForm:
    email: str = ""
    password: str = ""

    @classmethod
    def from_request(cls, form_data: dict) -> "LoginForm":
        return cls(
            email=str(form_data.get("email", "")).strip().lower(),
            password=str(form_data.get("password", "")),
        )
