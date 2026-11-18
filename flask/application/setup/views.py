from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from application.setup.forms import FirstBootForm
from application.ui_helpers import mask_secret
from domain.auth.services import AuthService
from domain.permissions.models import Preset, UserPermissions
from domain.permissions.services import PermissionService
from domain.personas.models import Gender
from domain.personas.services import PersonaService
from domain.settings.exceptions import InvalidLLMBackendError, SettingsError
from domain.settings.services import SettingsService
from infrastructure.image_gen.comfyui import ComfyUIImageGenProvider
from infrastructure.image_gen.google_ai import GoogleAIImageGenProvider
from infrastructure.llm.factory import get_llm_provider_class, probe_llm_backend
from infrastructure.llm.google_ai import GoogleAILLMProvider
from infrastructure.llm.ollama import OllamaLLMProvider
from infrastructure.provider_registry import ProviderRegistry
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.search.stub import SearXNGSearchStubProvider
from shared.exceptions import AimoError

setup_bp = Blueprint("setup", __name__, url_prefix="/setup")


@setup_bp.route("", methods=["GET", "POST"])
def first_boot():
    user_repo = UserRepository()
    if user_repo.count_users() > 0:
        return redirect(url_for("auth.login"))

    form = FirstBootForm.from_request(request.form if request.method == "POST" else {})
    env_google_key = GoogleAILLMProvider.DEFAULT_API_KEY.strip()

    if request.method == "POST":
        auth_service = AuthService()
        perm_service = PermissionService()
        settings_service = SettingsService()
        settings_repo = SettingsRepository()
        persona_service = PersonaService()
        persona_repo = PersonaRepository()

        try:
            admin_user = auth_service.create_user(
                username=form.username,
                email=form.email,
                password=form.password,
                is_initial_admin=True,
            )
        except AimoError as exc:
            form.active_step = 1
            flash(str(exc), "error")
            return _render_first_boot(form, env_google_key)

        try:
            settings = settings_repo.get_settings()
            effective_google_key = form.google_ai_api_key or env_google_key
            ProviderRegistry.update_backend_configuration(
                settings=settings,
                llm_backend=form.llm_backend,
                llm_configs={
                    OllamaLLMProvider.PROVIDER_ID: {"base_url": form.ollama_url},
                    GoogleAILLMProvider.PROVIDER_ID: {"api_key": effective_google_key},
                },
                image_gen_backend=form.image_gen_backend,
                image_gen_configs={
                    ComfyUIImageGenProvider.PROVIDER_ID: {"base_url": form.comfyui_url},
                    GoogleAIImageGenProvider.PROVIDER_ID: {"model": form.google_ai_image_model},
                },
                search_backend=form.search_backend,
                search_configs={
                    SearXNGSearchStubProvider.PROVIDER_ID: {"base_url": form.searxng_url},
                },
            )

            rec = get_llm_provider_class(settings.llm_backend).get_recommended_task_models()
            settings_service.update_task_models(
                settings=settings,
                roleplay_model=form.roleplay_model or rec["roleplay"],
                memory_model=form.memory_model or rec["memory"],
                assistant_model=form.assistant_model or rec["assistant"],
                vision_model=form.vision_model or rec["vision"],
                classification_model=form.classification_model or rec["classification"],
            )
        except InvalidLLMBackendError as exc:
            form.active_step = 2
            flash(str(exc), "error")
            return _render_first_boot(form, env_google_key)
        except (SettingsError, AimoError) as exc:
            form.active_step = 3
            flash(str(exc), "error")
            return _render_first_boot(form, env_google_key)

        saved_user = user_repo.create(admin_user)
        assert saved_user.id is not None

        user_perms = UserPermissions(user_id=saved_user.id)
        perm_service.assign_preset(saved_user, user_perms, Preset.ADMIN)
        user_repo.save_permissions(user_perms)

        settings_repo.save_settings(settings)

        default_persona = persona_service.create_persona(
            user_id=saved_user.id,
            name=saved_user.username,
            gender=Gender.NON_BINARY,
            portrait_path="portraits/default_persona.png",
            description="Abenteurer und Reisender.",
            appearance="Markante Gesichtszüge, wache Augen.",
            is_default=True,
        )
        persona_repo.create(default_persona)

        session["user_id"] = saved_user.id
        flash("Initialer Administrator und KI-Backend erfolgreich eingerichtet!", "success")
        return redirect(url_for("overview.index"))

    return _render_first_boot(form, env_google_key)


@setup_bp.route("/verify-backend", methods=["POST"])
def verify_backend():
    user_repo = UserRepository()
    if user_repo.count_users() > 0:
        abort(404)

    data = request.get_json(silent=True) or request.form.to_dict()
    raw_backend = str(data.get("llm_backend") or OllamaLLMProvider.PROVIDER_ID).strip().lower()
    submitted_cfg = {
        "base_url": str(data.get("ollama_url") or data.get("base_url") or "").strip(),
        "api_key": str(data.get("google_ai_api_key") or data.get("api_key") or "").strip()
        or GoogleAILLMProvider.DEFAULT_API_KEY.strip(),
    }

    result = probe_llm_backend(
        backend=raw_backend,
        submitted_config=submitted_cfg,
    )
    return jsonify(result)


def _render_first_boot(form: FirstBootForm, env_google_key: str):
    return render_template(
        "setup/first_boot.html",
        form=form,
        has_env_google_key=bool(env_google_key),
        env_google_key_hint=mask_secret(env_google_key),
        ollama_recommended=OllamaLLMProvider.get_recommended_models(),
        google_recommended=GoogleAILLMProvider.get_recommended_models(),
        recommended_by_backend=ProviderRegistry.get_recommended_task_models_by_backend(),
        recommended_google_image_model=GoogleAIImageGenProvider.get_recommended_model() or "",
        ollama_unique_models=OllamaLLMProvider.get_unique_recommended_models(),
    )
