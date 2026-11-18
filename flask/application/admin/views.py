from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.admin.forms import AdminPromptsForm, AdminServicesForm, AdminUserForm
from application.auth.decorators import require_permission
from application.ui_helpers import mask_secret
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
from domain.settings.models import (
    RECOMMENDED_ASSISTANT_MODEL,
    RECOMMENDED_CLASSIFICATION_MODEL,
    RECOMMENDED_GOOGLE_AI_IMAGE_MODEL,
    RECOMMENDED_MODELS,
    RECOMMENDED_ROLEPLAY_MODEL,
    ImageGenBackend,
    LLMBackend,
    SystemPrompts,
    get_recommended_models_for_backend,
    get_recommended_task_models,
)
from domain.settings.services import SettingsService
from infrastructure.image_gen.factory import get_image_gen_provider
from infrastructure.llm.factory import get_llm_provider
from infrastructure.llm.google_ai import GoogleAILLMProvider
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.user_repository import UserRepository
from infrastructure.repositories.worldinfo_repository import WorldInfoRepository
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

            flash(f"Benutzer '{saved_user.username}' erfolgreich angelegt.", "success")
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
        flash("Benutzer nicht gefunden.", "error")
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
            flash(f"Benutzer '{target_user.username}' aktualisiert.", "success")
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
        flash("Benutzer nicht gefunden.", "error")
        return redirect(url_for("admin.users_list"))

    try:
        perm_service.assert_modifiable_user(target_user)
        user_repo.delete(user_id)
        flash(f"Benutzer '{target_user.username}' gelöscht.", "success")
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
                settings = settings_service.apply_recommended_task_models(settings)
                settings = settings_repo.save_settings(settings)
                flash(
                    "Vorgeschlagene Modelle für alle 5 Rollen erfolgreich zugewiesen!",
                    "success",
                )
                return redirect(url_for("admin.services_config"))
            except AimoError as exc:
                flash(str(exc), "error")
        else:
            form = AdminServicesForm.from_request(request.form)
            try:
                previous_backend = settings.llm_backend
                settings_service.update_backend_configuration(
                    settings=settings,
                    llm_backend=form.llm_backend,
                    ollama_url=form.ollama_url,
                    google_ai_api_key=form.google_ai_api_key,
                    clear_google_ai_api_key=form.clear_google_ai_api_key,
                    image_gen_backend=form.image_gen_backend,
                    comfyui_url=form.comfyui_url,
                    google_ai_image_model=form.google_ai_image_model,
                    search_backend=form.search_backend,
                    searxng_url=form.searxng_url,
                )

                target_backend = settings.llm_backend
                rec = get_recommended_task_models(target_backend)

                def _resolve_submitted_model(submitted: str, role: str) -> str:
                    if (
                        previous_backend != target_backend
                        and not settings_service.is_model_compatible_with_backend(
                            submitted, target_backend
                        )
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
                flash("Service-Einstellungen und Modelle erfolgreich gespeichert.", "success")
                return redirect(url_for("admin.services_config"))
            except AimoError as exc:
                flash(str(exc), "error")

    llm = get_llm_provider(settings)
    img_gen = get_image_gen_provider(settings)

    llm_healthy = llm.check_health()
    image_gen_healthy = img_gen.check_health()
    installed_models: list[str] = []
    available_image_models: list[str] = []
    if llm_healthy:
        try:
            if isinstance(llm, GoogleAILLMProvider):
                installed_models, available_image_models = llm.list_model_catalog()
            else:
                installed_models = llm.list_models()
        except AimoError:
            installed_models = []

    unique_recommended = [
        RECOMMENDED_ROLEPLAY_MODEL,
        RECOMMENDED_ASSISTANT_MODEL,
        RECOMMENDED_CLASSIFICATION_MODEL,
    ]
    active_rec = get_recommended_task_models(settings.llm_backend)

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
            and settings_service.is_model_compatible_with_backend(assigned, settings.llm_backend)
        ):
            installed_models.append(assigned)

    for img_model in (RECOMMENDED_GOOGLE_AI_IMAGE_MODEL, settings.google_ai_image_model):
        if img_model and img_model not in available_image_models:
            available_image_models.append(img_model)

    return render_template(
        "admin/services.html",
        settings=settings,
        installed_models=installed_models,
        available_image_models=available_image_models,
        recommended_models=RECOMMENDED_MODELS,
        google_recommended_models=get_recommended_models_for_backend(LLMBackend.GOOGLE_AI),
        unique_recommended=unique_recommended,
        recommended_by_backend={
            LLMBackend.OLLAMA.value: get_recommended_task_models(LLMBackend.OLLAMA),
            LLMBackend.GOOGLE_AI.value: get_recommended_task_models(LLMBackend.GOOGLE_AI),
        },
        recommended_google_image_model=RECOMMENDED_GOOGLE_AI_IMAGE_MODEL,
        llm_healthy=llm_healthy,
        ollama_healthy=llm_healthy if settings.llm_backend == LLMBackend.OLLAMA else False,
        comfy_healthy=(
            image_gen_healthy
            if settings.image_gen_backend == ImageGenBackend.COMFYUI
            else False
        ),
        image_gen_healthy=image_gen_healthy,
        has_google_ai_api_key=bool(settings.google_ai_api_key),
        google_ai_api_key_hint=mask_secret(settings.google_ai_api_key),
    )


@admin_bp.route("/prompts", methods=["GET", "POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def prompts_config():
    settings_repo = SettingsRepository()
    settings_service = SettingsService()
    settings = settings_repo.get_settings()
    defaults = SystemPrompts()

    if request.method == "POST":
        form = AdminPromptsForm.from_request(request.form)
        try:
            settings_service.update_system_prompts(
                settings=settings,
                roleplay_prompt=form.roleplay_prompt,
                memory_prompt=form.memory_prompt,
                diffuser_prompt=form.diffuser_prompt,
                sparkle_assistant_prompt=form.sparkle_assistant_prompt,
                vision_persona_prompt=form.vision_persona_prompt,
                dialogue_author_prompt=form.dialogue_author_prompt,
            )
            settings = settings_repo.save_settings(settings)
            flash("System-Prompts erfolgreich gespeichert.", "success")
            return redirect(url_for("admin.prompts_config"))
        except AimoError as exc:
            flash(str(exc), "error")

    return render_template(
        "admin/prompts.html",
        settings=settings,
        defaults=defaults,
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
                flash("Systemweiter Standard-Backdrop zurückgesetzt (Standard-Design aktiv).", "success")
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
                    flash("Neuer systemweiter Standard-Backdrop erfolgreich gespeichert.", "success")
                    return redirect(url_for("admin.backdrop_config"))
                except AimoError as exc:
                    flash(str(exc), "error")
            else:
                flash("Bitte wählen Sie eine Bilddatei (PNG, JPG, WEBP) zum Hochladen aus.", "error")

        elif action == "select":
            selected_path = request.form.get("selected_backdrop_path", "").strip()
            if selected_path:
                try:
                    settings = settings_service.update_default_backdrop(settings, selected_path)
                    settings_repo.save_settings(settings)
                    flash("Systemweiter Standard-Backdrop erfolgreich zugewiesen.", "success")
                    return redirect(url_for("admin.backdrop_config"))
                except AimoError as exc:
                    flash(str(exc), "error")

    existing_locations_with_bg = []
    seen_paths = set()
    for wi in worldinfo_repo.list_all():
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
