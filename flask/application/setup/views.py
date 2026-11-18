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
from domain.settings.models import (
    RECOMMENDED_GOOGLE_AI_IMAGE_MODEL,
    LLMBackend,
    get_recommended_models_for_backend,
    get_recommended_task_models,
)
from domain.settings.services import SettingsService
from infrastructure.llm.factory import probe_llm_backend
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.user_repository import UserRepository
from shared.config import Config
from shared.exceptions import AimoError

setup_bp = Blueprint("setup", __name__, url_prefix="/setup")


@setup_bp.route("", methods=["GET", "POST"])
def first_boot():
    user_repo = UserRepository()
    if user_repo.count_users() > 0:
        return redirect(url_for("auth.login"))

    form = FirstBootForm.from_request(request.form if request.method == "POST" else {})
    env_google_key = Config.DEFAULT_GOOGLE_AI_API_KEY.strip()

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
            settings_service.update_backend_configuration(
                settings=settings,
                llm_backend=form.llm_backend,
                ollama_url=form.ollama_url,
                google_ai_api_key=effective_google_key,
                image_gen_backend=form.image_gen_backend,
                comfyui_url=form.comfyui_url,
                google_ai_image_model=form.google_ai_image_model,
                search_backend=form.search_backend,
                searxng_url=form.searxng_url,
            )

            rec = get_recommended_task_models(settings.llm_backend)
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
    raw_backend = str(data.get("llm_backend") or LLMBackend.OLLAMA.value).strip()
    ollama_url = str(data.get("ollama_url") or "").strip()
    raw_key = str(data.get("google_ai_api_key") or "").strip()
    effective_key = raw_key or Config.DEFAULT_GOOGLE_AI_API_KEY.strip()

    result = probe_llm_backend(
        backend=raw_backend,
        ollama_url=ollama_url,
        google_ai_api_key=effective_key,
    )
    return jsonify(result)


def _render_first_boot(form: FirstBootForm, env_google_key: str):
    return render_template(
        "setup/first_boot.html",
        form=form,
        has_env_google_key=bool(env_google_key),
        env_google_key_hint=mask_secret(env_google_key),
        ollama_recommended=get_recommended_models_for_backend(LLMBackend.OLLAMA),
        google_recommended=get_recommended_models_for_backend(LLMBackend.GOOGLE_AI),
        recommended_by_backend={
            LLMBackend.OLLAMA.value: get_recommended_task_models(LLMBackend.OLLAMA),
            LLMBackend.GOOGLE_AI.value: get_recommended_task_models(LLMBackend.GOOGLE_AI),
        },
        recommended_google_image_model=RECOMMENDED_GOOGLE_AI_IMAGE_MODEL,
        ollama_unique_models=list(
            dict.fromkeys(get_recommended_task_models(LLMBackend.OLLAMA).values())
        ),
    )
