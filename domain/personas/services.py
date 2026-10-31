from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from domain.personas.exceptions import InvalidPersonaDataError, PersonaInUseError
from domain.personas.models import Gender, UserPersona


class VisionAnalysisProvider(Protocol):
    def analyze_image(self, image_path: Path, prompt: str, model: str) -> str:
        ...


class PersonaService:
    def create_persona(
        self,
        user_id: int,
        name: str,
        gender: Gender | str,
        portrait_path: str,
        description: str,
        appearance: str = "",
        is_default: bool = False,
    ) -> UserPersona:
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise InvalidPersonaDataError("A valid positive user_id is required.")

        cleaned_name = name.strip() if isinstance(name, str) else ""
        if not cleaned_name:
            raise InvalidPersonaDataError("Persona name must not be empty.")

        try:
            resolved_gender = Gender.resolve(gender)
        except ValueError as exc:
            raise InvalidPersonaDataError(str(exc)) from exc

        cleaned_portrait = portrait_path.strip() if isinstance(portrait_path, str) else ""
        if not cleaned_portrait:
            raise InvalidPersonaDataError("Persona portrait_path must not be empty.")

        cleaned_desc = description.strip() if isinstance(description, str) else ""
        cleaned_appearance = appearance.strip() if isinstance(appearance, str) else ""

        return UserPersona(
            id=None,
            user_id=user_id,
            name=cleaned_name,
            gender=resolved_gender,
            portrait_path=cleaned_portrait,
            description=cleaned_desc,
            appearance=cleaned_appearance,
            is_default=bool(is_default),
            created_at=datetime.now(timezone.utc),
        )

    def update_persona(
        self,
        persona: UserPersona,
        name: str,
        gender: Gender | str,
        portrait_path: str,
        description: str,
        appearance: str,
    ) -> UserPersona:
        cleaned_name = name.strip() if isinstance(name, str) else ""
        if not cleaned_name:
            raise InvalidPersonaDataError("Persona name must not be empty.")

        try:
            resolved_gender = Gender.resolve(gender)
        except ValueError as exc:
            raise InvalidPersonaDataError(str(exc)) from exc

        cleaned_portrait = portrait_path.strip() if isinstance(portrait_path, str) else ""
        if not cleaned_portrait:
            raise InvalidPersonaDataError("Persona portrait_path must not be empty.")

        persona.name = cleaned_name
        persona.gender = resolved_gender
        persona.portrait_path = cleaned_portrait
        persona.description = description.strip() if isinstance(description, str) else ""
        persona.appearance = appearance.strip() if isinstance(appearance, str) else ""
        return persona

    def analyze_appearance(
        self,
        persona: UserPersona,
        vision_provider: VisionAnalysisProvider,
        vision_model: str,
        prompt: str,
        resolved_image_path: Path | None = None,
    ) -> str:
        target_path = (
            resolved_image_path
            if resolved_image_path is not None
            else Path(persona.portrait_path)
        )
        effective_prompt = (
            f"{prompt.strip()}\n"
            "Focus strictly on facial features, eye color, hairstyle, hair color, skin tone, "
            "and physical build. Ignore any backgrounds, lighting, or situational body poses."
        )
        extracted_appearance = vision_provider.analyze_image(
            image_path=target_path,
            prompt=effective_prompt,
            model=vision_model,
        ).strip()
        persona.appearance = extracted_appearance
        return extracted_appearance

    def delete_persona(self, persona: UserPersona, has_active_chats: bool) -> None:
        if has_active_chats:
            raise PersonaInUseError(
                f"Persona '{persona.name}' cannot be deleted because it is used in active chats."
            )

    def set_default_persona(
        self,
        user_id: int,
        persona_id: int,
        personas: list[UserPersona] | None = None,
    ) -> None:
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise InvalidPersonaDataError("A valid positive user_id is required.")
        if isinstance(persona_id, bool) or not isinstance(persona_id, int) or persona_id <= 0:
            raise InvalidPersonaDataError("A valid positive persona_id is required.")

        if personas is not None:
            for item in personas:
                if item.user_id == user_id:
                    item.is_default = item.id == persona_id
