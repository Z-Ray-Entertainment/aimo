import uuid
from pathlib import Path
from typing import BinaryIO

from shared.config import Config, _resolve_writable_dir
from shared.exceptions import InfrastructureError
from shared.utils import sanitize_filename

ALLOWED_IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".webp"}
)

_PNG_SIGNATURE: bytes = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE: bytes = b"\xff\xd8\xff"
_WEBP_RIFF_SIGNATURE: bytes = b"RIFF"
_WEBP_FORMAT_SIGNATURE: bytes = b"WEBP"


class FileStorage:
    def __init__(self, base_upload_dir: Path = Config.UPLOAD_DIR) -> None:
        self.base_upload_dir: Path = _resolve_writable_dir(
            Path(base_upload_dir).resolve(), "uploads"
        )
        self.portraits_dir: Path = self.base_upload_dir / "portraits"
        self.sprites_dir: Path = self.base_upload_dir / "sprites"
        self.backgrounds_dir: Path = self.base_upload_dir / "backgrounds"
        self.generated_dir: Path = self.base_upload_dir / "generated"

        for directory in (
            self.base_upload_dir,
            self.portraits_dir,
            self.sprites_dir,
            self.backgrounds_dir,
            self.generated_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def get_character_sprites_dir(self, character_id: int) -> Path:
        if isinstance(character_id, bool) or not isinstance(character_id, int) or character_id <= 0:
            raise InfrastructureError("character_id must be a positive integer.")
        sprite_dir = (self.sprites_dir / str(character_id)).resolve()
        self._assert_within_base(sprite_dir)
        sprite_dir.mkdir(parents=True, exist_ok=True)
        return sprite_dir

    def save_portrait(self, content: bytes | BinaryIO, filename: str) -> str:
        return self._save_to_directory(
            target_dir=self.portraits_dir,
            content=content,
            filename=filename,
            unique_prefix=True,
        )

    def save_sprite(
        self,
        character_id: int,
        content: bytes | BinaryIO,
        filename: str,
        emotion: str | None = None,
        variant: int | None = None,
    ) -> str:
        target_dir = self.get_character_sprites_dir(character_id)
        extension = self.validate_image_filename(filename)
        raw_bytes = self._extract_bytes(content)
        self.validate_image_bytes(raw_bytes, extension)

        if emotion is not None and variant is not None:
            safe_emotion = sanitize_filename(emotion).lower()
            target_filename = f"{safe_emotion}_{int(variant)}{extension}"
            return self._write_bytes(target_dir / target_filename, raw_bytes)

        return self._save_to_directory(
            target_dir=target_dir,
            content=raw_bytes,
            filename=filename,
            unique_prefix=False,
        )

    def save_background(self, content: bytes | BinaryIO, filename: str) -> str:
        return self._save_to_directory(
            target_dir=self.backgrounds_dir,
            content=content,
            filename=filename,
            unique_prefix=True,
        )

    def save_generated_image(self, content: bytes | BinaryIO, filename: str) -> str:
        return self._save_to_directory(
            target_dir=self.generated_dir,
            content=content,
            filename=filename,
            unique_prefix=True,
        )

    def allocate_generated_path(self, filename: str = "generated.png") -> Path:
        extension = self.validate_image_filename(filename)
        stem = sanitize_filename(Path(filename).stem)
        unique_name = f"{uuid.uuid4().hex[:12]}_{stem}{extension}"
        target_path = (self.generated_dir / unique_name).resolve()
        self._assert_within_base(target_path)
        return target_path

    def resolve_path(self, relative_or_abs_path: str | Path) -> Path:
        candidate = Path(relative_or_abs_path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            parts = candidate.parts
            if parts and parts[0] == "uploads":
                candidate = Path(*parts[1:]) if len(parts) > 1 else Path()
            resolved = (self.base_upload_dir / candidate).resolve()
        self._assert_within_base(resolved)
        return resolved

    def to_relative_path(self, full_path: str | Path) -> str:
        resolved = self.resolve_path(full_path)
        return resolved.relative_to(self.base_upload_dir).as_posix()

    def delete_file(self, relative_or_abs_path: str | Path) -> bool:
        resolved = self.resolve_path(relative_or_abs_path)
        if not resolved.is_file():
            return False
        try:
            resolved.unlink()
            return True
        except OSError as exc:
            raise InfrastructureError(
                f"Failed to delete file '{resolved}': {exc}"
            ) from exc

    @staticmethod
    def validate_image_filename(filename: str) -> str:
        if not isinstance(filename, str) or not filename.strip():
            raise InfrastructureError("Image filename must not be empty.")
        extension = Path(filename.strip()).suffix.lower()
        if extension not in ALLOWED_IMAGE_EXTENSIONS:
            allowed_display = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
            raise InfrastructureError(
                f"Unsupported image format '{extension or '<none>'}'. "
                f"Allowed formats: {allowed_display}."
            )
        return extension

    @staticmethod
    def validate_image_bytes(data: bytes, extension: str | None = None) -> None:
        if not data:
            raise InfrastructureError("Uploaded image data must not be empty.")

        is_png = data.startswith(_PNG_SIGNATURE)
        is_jpeg = data.startswith(_JPEG_SIGNATURE)
        is_webp = (
            len(data) >= 12
            and data[:4] == _WEBP_RIFF_SIGNATURE
            and data[8:12] == _WEBP_FORMAT_SIGNATURE
        )

        if not (is_png or is_jpeg or is_webp):
            raise InfrastructureError(
                "Invalid image content: file header does not match PNG, JPG, or WEBP."
            )

        if extension is not None:
            norm_ext = extension.lower()
            if norm_ext == ".png" and not is_png:
                raise InfrastructureError(
                    "File extension '.png' does not match binary image header."
                )
            if norm_ext in (".jpg", ".jpeg") and not is_jpeg:
                raise InfrastructureError(
                    f"File extension '{norm_ext}' does not match binary image header."
                )
            if norm_ext == ".webp" and not is_webp:
                raise InfrastructureError(
                    "File extension '.webp' does not match binary image header."
                )

    def _save_to_directory(
        self,
        target_dir: Path,
        content: bytes | BinaryIO,
        filename: str,
        unique_prefix: bool,
    ) -> str:
        extension = self.validate_image_filename(filename)
        raw_bytes = self._extract_bytes(content)
        self.validate_image_bytes(raw_bytes, extension)

        safe_stem = sanitize_filename(Path(filename).stem)
        if unique_prefix:
            final_name = f"{uuid.uuid4().hex[:12]}_{safe_stem}{extension}"
        else:
            final_name = f"{safe_stem}{extension}"

        target_path = (target_dir / final_name).resolve()
        return self._write_bytes(target_path, raw_bytes)

    def _write_bytes(self, target_path: Path, data: bytes) -> str:
        resolved = target_path.resolve()
        self._assert_within_base(resolved)
        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_bytes(data)
        except OSError as exc:
            raise InfrastructureError(
                f"Failed to write image file '{resolved}': {exc}"
            ) from exc
        return resolved.relative_to(self.base_upload_dir).as_posix()

    def _assert_within_base(self, target_path: Path) -> None:
        try:
            target_path.relative_to(self.base_upload_dir)
        except ValueError as exc:
            raise InfrastructureError(
                f"Path '{target_path}' escapes the configured upload directory."
            ) from exc

    @staticmethod
    def _extract_bytes(content: bytes | BinaryIO) -> bytes:
        if isinstance(content, (bytes, bytearray)):
            return bytes(content)
        if hasattr(content, "read"):
            data = content.read()
            if isinstance(data, str):
                return data.encode("utf-8")
            return bytes(data)
        raise InfrastructureError("Unsupported image content source.")
