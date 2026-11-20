from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.admin.forms import AdminPromptsForm, AdminServicesForm, AdminUserForm
from application.auth.decorators import require_permission
from application.ui_helpers import mask_secret, tr
from i18n import gettext_noop as _
from domain.auth.services import AuthService
from domain.permissions.models import (
    PRESET_PERMISSIONS,
    FunctionPermission,
    Preset,
    UserPermissions,
)
from domain.permissions.services import PermissionService
from domain.personas.models import Gender
from domain.personas.services import PersonaService
from domain.settings.models import SystemPrompts
from domain.settings.services import SettingsService
from infrastructure.image_gen.comfyui import ComfyUIImageGenProvider
from infrastructure.image_gen.factory import get_image_gen_provider
from infrastructure.image_gen.google_ai import GoogleAIImageGenProvider
from infrastructure.llm.factory import get_llm_provider, get_llm_provider_class
from infrastructure.llm.google_ai import GoogleAILLMProvider
from infrastructure.llm.ollama import OllamaLLMProvider
from infrastructure.provider_registry import ProviderRegistry
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
from infrastructure.search.stub import SearXNGSearchStubProvider
from infrastructure.storage.file_storage import FileStorage
from shared.exceptions import AimoError

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def index():
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/users", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def users_list():
    user_repo = UserRepository()
    users = user_repo.list_all()
    user_items = []
    for u in users:
        perms = user_repo.get_permissions(u.id or 0)
        user_items.append(
            {
                "user": u,
                "permissions": sorted(perms.permissions),
            }
        )
    return render_template("admin/users.html", user_items=user_items)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def create_user():
    user_repo = UserRepository()
    auth_service = AuthService()
    perm_service = PermissionService()
    persona_service = PersonaService()
    persona_repo = PersonaRepository()

    form = AdminUserForm.from_request(request.form) if request.method == "POST" else AdminUserForm(preset=Preset.USER.value)

    if request.method == "POST":
        try:
            existing = user_repo.get_by_email(form.email)
            if existing is not None:
                raise AimoError("Ein Benutzer mit dieser E-Mail-Adresse existiert bereits.")

            new_user = auth_service.create_user(
                username=form.username,
                email=form.email,
                password=form.password,
                is_initial_admin=False,
            )
            saved_user = user_repo.create(new_user)
            assert saved_user.id is not None

            user_perms = UserPermissions(user_id=saved_user.id)
            if form.preset:
                perm_service.assign_preset(saved_user, user_perms, form.preset)
            else:
                for perm_str in form.permissions:
                    perm_service.grant_permission(saved_user, user_perms, perm_str)

            user_repo.save_permissions(user_perms)

            default_persona = persona_service.create_persona(
                user_id=saved_user.id,
                name=saved_user.username,
                gender=Gender.NON_BINARY,
                portrait_path="portraits/default_persona.png",
                description="Spieler-Persona.",
                appearance="",
                is_default=True,
            )
            persona_repo.create(default_persona)

            flash(tr(_("User '%(username)s' created successfully."), username=saved_user.username), "success")
            return redirect(url_for("admin.users_list"))
        except (AimoError, ValueError) as exc:
            flash(str(exc), "error")

    return render_template(
        "admin/user_form.html",
        target_user=None,
        form=form,
        all_permissions=[p.value for p in FunctionPermission],
        presets=[p.value for p in Preset],
        preset_map={k.value: sorted(v) for k, v in PRESET_PERMISSIONS.items()},
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def edit_user(user_id: int):
    user_repo = UserRepository()
    auth_service = AuthService()
    perm_service = PermissionService()

    target_user = user_repo.get_by_id(user_id)
    if target_user is None:
        flash(tr(_("User not found.")), "error")
        return redirect(url_for("admin.users_list"))

    current_perms = user_repo.get_permissions(user_id)

    if request.method == "POST":
        form = AdminUserForm.from_request(request.form)
        try:
            if form.username:
                target_user.username = form.username
            if form.email:
                target_user.email = form.email
            if form.password.strip():
                auth_service.change_password(target_user, form.password.strip())

            new_perms = UserPermissions(user_id=user_id, permissions=set(current_perms.permissions))
            if form.preset:
                perm_service.assign_preset(target_user, new_perms, form.preset)
            else:
                requested_set = {FunctionPermission.resolve(p).value for p in form.permissions}
                for existing_p in list(new_perms.permissions):
                    if existing_p not in requested_set:
                        perm_service.revoke_permission(target_user, new_perms, existing_p)
                for req_p in requested_set:
                    perm_service.grant_permission(target_user, new_perms, req_p)

            user_repo.update(target_user)
            user_repo.save_permissions(new_perms)
            flash(tr(_("User '%(username)s' updated."), username=target_user.username), "success")
            return redirect(url_for("admin.users_list"))
        except (AimoError, ValueError) as exc:
            flash(str(exc), "error")
    else:
        form = AdminUserForm(
            username=target_user.username,
            email=target_user.email,
            permissions=sorted(current_perms.permissions),
        )

    return render_template(
        "admin/user_form.html",
        target_user=target_user,
        form=form,
        all_permissions=[p.value for p in FunctionPermission],
        presets=[p.value for p in Preset],
        preset_map={k.value: sorted(v) for k, v in PRESET_PERMISSIONS.items()},
    )


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def delete_user(user_id: int):
    user_repo = UserRepository()
    perm_service = PermissionService()

    target_user = user_repo.get_by_id(user_id)
    if target_user is None:
        flash(tr(_("User not found.")), "error")
        return redirect(url_for("admin.users_list"))

    try:
        perm_service.assert_modifiable_user(target_user)
        user_repo.delete(user_id)
        flash(tr(_("User '%(username)s' deleted."), username=target_user.username), "success")
    except AimoError as exc:
        flash(str(exc), "error")

    return redirect(url_for("admin.users_list"))


@admin_bp.route("/services", methods=["GET", "POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def services_config():
    settings_repo = SettingsRepository()
    settings_service = SettingsService()
    settings = settings_repo.get_settings()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "apply_recommended":
            try:
                settings = ProviderRegistry.apply_recommended_models(settings)
                settings = settings_repo.save_settings(settings)
                flash(
                    tr(_("Suggested models assigned for all 5 roles successfully!")),
                    "success",
                )
                return redirect(url_for("admin.services_config"))
            except AimoError as exc:
                flash(str(exc), "error")
        else:
            form = AdminServicesForm.from_request(request.form)
            try:
                previous_backend = settings.llm_backend
                clear_secrets = (
                    {GoogleAILLMProvider.PROVIDER_ID}
                    if form.clear_google_ai_api_key
                    else set()
                )
                ProviderRegistry.update_backend_configuration(
                    settings=settings,
                    llm_backend=form.llm_backend,
                    llm_configs={
                        OllamaLLMProvider.PROVIDER_ID: {"base_url": form.ollama_url},
                        GoogleAILLMProvider.PROVIDER_ID: {"api_key": form.google_ai_api_key},
                    },
                    clear_llm_secrets=clear_secrets,
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

                target_llm_cls = get_llm_provider_class(settings.llm_backend)
                rec = target_llm_cls.get_recommended_task_models()

                def _resolve_submitted_model(submitted: str, role: str) -> str:
                    if (
                        previous_backend != settings.llm_backend
                        and not target_llm_cls.is_model_compatible(submitted)
                    ):
                        return rec[role]
                    return submitted or rec[role]

                settings_service.update_task_models(
                    settings=settings,
                    roleplay_model=_resolve_submitted_model(form.roleplay_model, "roleplay"),
                    memory_model=_resolve_submitted_model(form.memory_model, "memory"),
                    assistant_model=_resolve_submitted_model(form.assistant_model, "assistant"),
                    vision_model=_resolve_submitted_model(form.vision_model, "vision"),
                    classification_model=_resolve_submitted_model(
                        form.classification_model, "classification"
                    ),
                )
                settings_service.update_parameters(
                    settings=settings,
                    num_ctx=form.num_ctx,
                    temperature=form.temperature,
                    top_p=form.top_p,
                    repeat_penalty=form.repeat_penalty,
                )
                settings = settings_repo.save_settings(settings)
                flash(tr(_("Service settings and models saved successfully.")), "success")
                return redirect(url_for("admin.services_config"))
            except AimoError as exc:
                flash(str(exc), "error")

    llm = get_llm_provider(settings)
    llm_cls = get_llm_provider_class(settings.llm_backend)
    img_gen = get_image_gen_provider(settings)

    llm_healthy = llm.check_health()
    image_gen_healthy = img_gen.check_health()
    installed_models: list[str] = []
    available_image_models: list[str] = []
    if llm_healthy:
        try:
            installed_models, available_image_models = llm.list_model_catalog()
        except AimoError:
            installed_models = []

    active_rec = llm_cls.get_recommended_task_models()
    for assigned in (
        *active_rec.values(),
        settings.tasks.roleplay_model,
        settings.tasks.memory_model,
        settings.tasks.assistant_model,
        settings.tasks.classification_model,
        settings.tasks.vision_model,
    ):
        if (
            assigned
            and assigned not in installed_models
            and llm_cls.is_model_compatible(assigned)
        ):
            installed_models.append(assigned)

    rec_google_img_model = GoogleAIImageGenProvider.get_recommended_model() or ""
    saved_google_img_model = settings.get_image_gen_config(
        GoogleAIImageGenProvider.PROVIDER_ID
    ).get("model", rec_google_img_model)
    for img_model in (rec_google_img_model, saved_google_img_model):
        if img_model and img_model not in available_image_models:
            available_image_models.append(img_model)

    google_api_key = settings.get_llm_config(GoogleAILLMProvider.PROVIDER_ID).get("api_key", "")
    ollama_url = settings.get_llm_config(OllamaLLMProvider.PROVIDER_ID).get(
        "base_url", OllamaLLMProvider.DEFAULT_BASE_URL
    )
    comfyui_url = settings.get_image_gen_config(ComfyUIImageGenProvider.PROVIDER_ID).get(
        "base_url", ComfyUIImageGenProvider.DEFAULT_BASE_URL
    )
    searxng_url = settings.get_search_config(SearXNGSearchStubProvider.PROVIDER_ID).get(
        "base_url", SearXNGSearchStubProvider.DEFAULT_BASE_URL
    )

    ollama_grouped_recommended = _group_recommended_models_for_ui(
        OllamaLLMProvider.get_recommended_models()
    )

    return render_template(
        "admin/services.html",
        settings=settings,
        ollama_url=ollama_url,
        comfyui_url=comfyui_url,
        searxng_url=searxng_url,
        google_ai_image_model=saved_google_img_model,
        installed_models=installed_models,
        available_image_models=available_image_models,
        ollama_grouped_recommended=ollama_grouped_recommended,
        ollama_unique_models=OllamaLLMProvider.get_unique_recommended_models(),
        google_recommended_models=GoogleAILLMProvider.get_recommended_models(),
        recommended_by_backend=ProviderRegistry.get_recommended_task_models_by_backend(),
        recommended_google_image_model=rec_google_img_model,
        llm_healthy=llm_healthy,
        ollama_healthy=(
            llm_healthy if llm_cls.supports_model_management() else False
        ),
        comfy_healthy=(
            image_gen_healthy
            if settings.image_gen_backend == ComfyUIImageGenProvider.PROVIDER_ID
            else False
        ),
        image_gen_healthy=image_gen_healthy,
        has_google_ai_api_key=bool(google_api_key),
        google_ai_api_key_hint=mask_secret(google_api_key),
    )


def _group_recommended_models_for_ui(
    role_models: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    grouped: dict[str, list[str]] = {}
    for info in role_models.values():
        model_id = info.get("model", "")
        role_name = info.get("role_name", "")
        if model_id:
            grouped.setdefault(model_id, []).append(role_name)
    return [{"model": model_id, "roles": roles} for model_id, roles in grouped.items()]


@admin_bp.route("/prompts", methods=["GET", "POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def prompts_config():
    from domain.settings.models import PROMPT_KEYS, get_default_prompt, is_default_prompt
    from domain.translation.models import SUPPORTED_LANGUAGES
    from infrastructure.llm.factory import get_llm_provider_class
    from infrastructure.repositories.translation_repository import TranslationRepository
    import requests as http_requests
    from application.core_client import build_core_headers, get_core_base_url

    settings_repo = SettingsRepository()
    settings_service = SettingsService()
    trans_repo = TranslationRepository()
    settings = settings_repo.get_settings()
    defaults = SystemPrompts()

    if request.method == "POST":
        form = AdminPromptsForm.from_request(request.form)
        try:
            settings_service.update_system_prompts(
                settings=settings,
                roleplay_prompt=form.roleplay_prompt,
                memory_prompt=form.memory_prompt,
                diffuser_prompt=form.diffuser_prompt or settings.prompts.diffuser_prompt,
                sparkle_assistant_prompt=form.sparkle_assistant_prompt,
                vision_persona_prompt=form.vision_persona_prompt,
                dialogue_author_prompt=form.dialogue_author_prompt,
            )
            settings = settings_repo.save_settings(settings)
            for key in PROMPT_KEYS:
                current_val = getattr(settings.prompts, key, "")
                if is_default_prompt(key, current_val):
                    trans_repo.delete_field_translations("system_prompt", 1, key)
                else:
                    raw_i18n = request.form.get(f"i18n_{key}", "").strip()
                    if raw_i18n:
                        trans_repo.save_field_variants_json("system_prompt", 1, key, raw_i18n)
            try:
                http_requests.post(
                    f"{get_core_base_url()}/api/admin/translations/notify",
                    headers=build_core_headers(),
                    timeout=2,
                )
            except Exception:
                pass
            flash(tr(_("System prompts saved successfully.")), "success")
            return redirect(url_for("admin.prompts_config"))
        except AimoError as exc:
            flash(str(exc), "error")

    prompt_variants: dict[str, dict[str, dict]] = {}
    default_prompt_variants: dict[str, dict[str, dict]] = {}
    for key in PROMPT_KEYS:
        default_map = {
            lang: {"content": get_default_prompt(key, lang), "text": get_default_prompt(key, lang), "is_outdated": False, "outdated": False}
            for lang in SUPPORTED_LANGUAGES
        }
        default_prompt_variants[key] = default_map
        current_val = getattr(settings.prompts, key, "")
        if is_default_prompt(key, current_val):
            prompt_variants[key] = default_map
        else:
            stored = trans_repo.get_field_translations("system_prompt", 1, key)
            if "en" not in stored and current_val:
                stored["en"] = {"content": current_val, "text": current_val, "is_outdated": False, "outdated": False}
            prompt_variants[key] = stored

    is_cloud_llm = get_llm_provider_class(settings.llm_backend).is_cloud_provider()

    return render_template(
        "admin/prompts.html",
        settings=settings,
        defaults=defaults,
        prompt_variants=prompt_variants,
        default_prompt_variants=default_prompt_variants,
        is_cloud_llm=is_cloud_llm,
    )


@admin_bp.route("/backdrop", methods=["GET", "POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def backdrop_config():
    settings_repo = SettingsRepository()
    settings_service = SettingsService()
    settings = settings_repo.get_settings()
    storage = FileStorage()
    worldinfo_repo = WorldInfoRepository()

    if request.method == "POST":
        action = request.form.get("action", "")
        if action == "clear" or "clear" in request.form:
            try:
                settings = settings_service.update_default_backdrop(settings, None)
                settings_repo.save_settings(settings)
                flash(tr(_("System-wide default backdrop reset (default theme active).")), "success")
                return redirect(url_for("admin.backdrop_config"))
            except AimoError as exc:
                flash(str(exc), "error")

        elif action == "upload" or "backdrop_file" in request.files:
            file_obj = request.files.get("backdrop_file")
            if file_obj and file_obj.filename:
                try:
                    rel_path = storage.save_background(file_obj.stream, file_obj.filename)
                    settings = settings_service.update_default_backdrop(settings, rel_path)
                    settings_repo.save_settings(settings)
                    flash(tr(_("New system-wide default backdrop saved successfully.")), "success")
                    return redirect(url_for("admin.backdrop_config"))
                except AimoError as exc:
                    flash(str(exc), "error")
            else:
                flash(tr(_("Please select an image file (PNG, JPG, WEBP) to upload.")), "error")

        elif action == "select":
            selected_path = request.form.get("selected_backdrop_path", "").strip()
            if selected_path:
                try:
                    settings = settings_service.update_default_backdrop(settings, selected_path)
                    settings_repo.save_settings(settings)
                    flash(tr(_("System-wide default backdrop assigned successfully.")), "success")
                    return redirect(url_for("admin.backdrop_config"))
                except AimoError as exc:
                    flash(str(exc), "error")

    existing_locations_with_bg = []
    seen_paths = set()
    for wi in worldinfo_repo.list_all():
        if wi.backdrop_image_path and wi.backdrop_image_path not in seen_paths:
            seen_paths.add(wi.backdrop_image_path)
            existing_locations_with_bg.append(
                {
                    "worldinfo_name": wi.name,
                    "location_name": tr(_("World Backdrop")),
                    "path": wi.backdrop_image_path,
                }
            )
        if wi.id is not None:
            for loc in worldinfo_repo.list_locations(wi.id):
                if loc.background_image_path and loc.background_image_path not in seen_paths:
                    seen_paths.add(loc.background_image_path)
                    existing_locations_with_bg.append(
                        {
                            "worldinfo_name": wi.name,
                            "location_name": loc.name,
                            "path": loc.background_image_path,
                        }
                    )

    return render_template(
        "admin/backdrop.html",
        settings=settings,
        existing_locations_with_bg=existing_locations_with_bg,
    )


@admin_bp.route("/translations", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def translations_config():
    return render_template("admin/translations.html")
