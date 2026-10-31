import time
import uuid
from pathlib import Path
from typing import Any

import requests

from infrastructure.image_gen.interface import ImageGenProvider
from shared.config import Config
from shared.exceptions import InfrastructureError


class ComfyUIImageGenProvider(ImageGenProvider):
    def __init__(
        self,
        base_url: str = Config.DEFAULT_COMFYUI_URL,
        checkpoint_name: str = "v1-5-pruned-emaonly.safetensors",
        request_timeout: tuple[float, float] = (10.0, 30.0),
        generation_timeout_seconds: float = 300.0,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self.base_url: str = base_url.strip().rstrip("/")
        self.checkpoint_name: str = checkpoint_name
        self.request_timeout: tuple[float, float] = request_timeout
        self.generation_timeout_seconds: float = generation_timeout_seconds
        self.poll_interval_seconds: float = poll_interval_seconds
        self._cancelled_tasks: set[str] = set()

    def generate_image(
        self,
        prompt: str,
        reference_images: list[Path],
        negative_prompt: str,
        output_path: Path,
    ) -> Path:
        cleaned_prompt = prompt.strip()
        if not cleaned_prompt:
            raise InfrastructureError(
                "Image generation prompt must not be empty."
            )

        uploaded_filenames: list[str] = []
        for ref_path in reference_images:
            resolved_ref = Path(ref_path).resolve()
            if resolved_ref.is_file():
                uploaded_filenames.append(self._upload_reference_image(resolved_ref))

        workflow = self._build_workflow(
            positive_prompt=cleaned_prompt,
            negative_prompt=negative_prompt.strip(),
            uploaded_references=uploaded_filenames,
        )
        client_id = str(uuid.uuid4())
        prompt_id = self._submit_prompt(workflow=workflow, client_id=client_id)

        image_meta = self._wait_for_completion(prompt_id=prompt_id)
        image_bytes = self._download_generated_image(image_meta=image_meta)

        target_path = Path(output_path).resolve()
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(image_bytes)
        except OSError as exc:
            raise InfrastructureError(
                f"Failed to save generated image to '{target_path}': {exc}"
            ) from exc

        return target_path

    def cancel_generation(self, task_id: str) -> None:
        cleaned_id = task_id.strip() if isinstance(task_id, str) else ""
        if cleaned_id:
            self._cancelled_tasks.add(cleaned_id)

        try:
            if cleaned_id:
                requests.post(
                    f"{self.base_url}/queue",
                    json={"delete": [cleaned_id]},
                    timeout=self.request_timeout,
                )
            interrupt_response = requests.post(
                f"{self.base_url}/interrupt",
                timeout=self.request_timeout,
            )
            self._ensure_ok(interrupt_response, "ComfyUI interrupt generation")
        except requests.RequestException as exc:
            raise InfrastructureError(
                f"Failed to cancel ComfyUI image generation at '{self.base_url}': {exc}"
            ) from exc

    def check_health(self) -> bool:
        if not self.base_url:
            return False
        try:
            response = requests.get(
                f"{self.base_url}/system_stats",
                timeout=(1.5, 2.0),
            )
            return response.status_code == 200
        except requests.RequestException:
            return False

    def _upload_reference_image(self, image_path: Path) -> str:
        try:
            with image_path.open("rb") as file_handle:
                response = requests.post(
                    f"{self.base_url}/upload/image",
                    files={"image": (image_path.name, file_handle)},
                    data={"overwrite": "true"},
                    timeout=self.request_timeout,
                )
            self._ensure_ok(
                response, f"ComfyUI upload reference image '{image_path.name}'"
            )
            data = response.json()
        except (OSError, requests.RequestException, ValueError) as exc:
            raise InfrastructureError(
                f"Failed to upload reference image '{image_path}' to ComfyUI: {exc}"
            ) from exc

        uploaded_name = data.get("name")
        if not uploaded_name:
            raise InfrastructureError(
                f"ComfyUI upload response did not return a filename for '{image_path.name}'."
            )
        return str(uploaded_name)

    def _build_workflow(
        self,
        positive_prompt: str,
        negative_prompt: str,
        uploaded_references: list[str],
    ) -> dict[str, Any]:
        seed = uuid.uuid4().int & ((1 << 32) - 1)
        workflow: dict[str, Any] = {
            "1": {
                "class_type": "CheckpointLoaderSimple",
                "inputs": {
                    "ckpt_name": self.checkpoint_name,
                },
            },
            "2": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": positive_prompt,
                    "clip": ["1", 1],
                },
            },
            "3": {
                "class_type": "CLIPTextEncode",
                "inputs": {
                    "text": negative_prompt,
                    "clip": ["1", 1],
                },
            },
            "4": {
                "class_type": "EmptyLatentImage",
                "inputs": {
                    "width": 1024,
                    "height": 576,
                    "batch_size": 1,
                },
            },
            "5": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": 20,
                    "cfg": 7.0,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["2", 0],
                    "negative": ["3", 0],
                    "latent_image": ["4", 0],
                },
            },
            "6": {
                "class_type": "VAEDecode",
                "inputs": {
                    "samples": ["5", 0],
                    "vae": ["1", 2],
                },
            },
            "7": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "aimo_gen",
                    "images": ["6", 0],
                },
            },
        }

        for idx, ref_filename in enumerate(uploaded_references, start=10):
            workflow[str(idx)] = {
                "class_type": "LoadImage",
                "inputs": {
                    "image": ref_filename,
                },
            }

        return workflow

    def _submit_prompt(self, workflow: dict[str, Any], client_id: str) -> str:
        try:
            response = requests.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": client_id},
                timeout=self.request_timeout,
            )
            self._ensure_ok(response, "ComfyUI submit workflow prompt")
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise InfrastructureError(
                f"Failed to submit workflow prompt to ComfyUI at '{self.base_url}': {exc}"
            ) from exc

        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise InfrastructureError(
                f"ComfyUI response did not contain a valid 'prompt_id': {data}"
            )
        return str(prompt_id)

    def _wait_for_completion(self, prompt_id: str) -> dict[str, str]:
        deadline = time.monotonic() + self.generation_timeout_seconds
        while time.monotonic() < deadline:
            if prompt_id in self._cancelled_tasks:
                self._cancelled_tasks.discard(prompt_id)
                raise InfrastructureError(
                    f"ComfyUI image generation task '{prompt_id}' was cancelled."
                )

            try:
                response = requests.get(
                    f"{self.base_url}/history/{prompt_id}",
                    timeout=self.request_timeout,
                )
                self._ensure_ok(response, f"ComfyUI poll history '{prompt_id}'")
                history_data = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise InfrastructureError(
                    f"Failed while polling ComfyUI history for '{prompt_id}': {exc}"
                ) from exc

            if isinstance(history_data, dict) and prompt_id in history_data:
                task_entry = history_data[prompt_id]
                status_info = (
                    task_entry.get("status", {})
                    if isinstance(task_entry, dict)
                    else {}
                )
                if status_info.get("status_str") == "error":
                    raise InfrastructureError(
                        f"ComfyUI workflow execution failed for task '{prompt_id}'."
                    )

                outputs = (
                    task_entry.get("outputs", {})
                    if isinstance(task_entry, dict)
                    else {}
                )
                image_meta = self._extract_first_image_meta(outputs)
                if image_meta is not None:
                    return image_meta

            time.sleep(self.poll_interval_seconds)

        raise InfrastructureError(
            f"ComfyUI image generation timed out after {self.generation_timeout_seconds}s "
            f"(prompt_id='{prompt_id}')."
        )

    @staticmethod
    def _extract_first_image_meta(outputs: Any) -> dict[str, str] | None:
        if not isinstance(outputs, dict):
            return None
        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            images = node_output.get("images", [])
            if isinstance(images, list) and images:
                first = images[0]
                if isinstance(first, dict) and first.get("filename"):
                    return {
                        "filename": str(first["filename"]),
                        "subfolder": str(first.get("subfolder", "")),
                        "type": str(first.get("type", "output")),
                    }
        return None

    def _download_generated_image(self, image_meta: dict[str, str]) -> bytes:
        try:
            response = requests.get(
                f"{self.base_url}/view",
                params=image_meta,
                timeout=self.request_timeout,
            )
            self._ensure_ok(response, "ComfyUI download generated image")
            return response.content
        except requests.RequestException as exc:
            raise InfrastructureError(
                f"Failed to download generated image from ComfyUI: {exc}"
            ) from exc

    @staticmethod
    def _ensure_ok(response: requests.Response, context: str) -> None:
        if response.status_code >= 400:
            detail = response.text.strip()
            raise InfrastructureError(
                f"{context} failed with HTTP {response.status_code}: {detail}"
            )
