from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from application.setup.forms import FirstBootForm
from domain.auth.services import AuthService
from domain.permissions.models import Preset, UserPermissions
from domain.permissions.services import PermissionService
from domain.personas.models import Gender
from domain.personas.services import PersonaService
from domain.settings.services import SettingsService
from infrastructure.repositories.persona_repository import PersonaRepository
from infrastructure.repositories.settings_repository import SettingsRepository
from infrastructure.repositories.user_repository import UserRepository
from shared.exceptions import AimoError

setup_bp = Blueprint("setup", __name__, url_prefix="/setup")


@setup_bp.route("", methods=["GET", "POST"])
def first_boot():
    user_repo = UserRepository()
    if user_repo.count_users() > 0:
        return redirect(url_for("auth.login"))

    form = FirstBootForm.from_request(request.form if request.method == "POST" else {})
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
            saved_user = user_repo.create(admin_user)
            assert saved_user.id is not None

            user_perms = UserPermissions(user_id=saved_user.id)
            perm_service.assign_preset(saved_user, user_perms, Preset.ADMIN)
            user_repo.save_permissions(user_perms)

            settings = settings_repo.get_settings()
            settings_service.update_service_urls(
                settings=settings,
                ollama_url=form.ollama_url,
                comfyui_url=form.comfyui_url,
                searxng_url=form.searxng_url,
                searxng_enabled=False,
            )
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
            flash("Initialer Administrator und System-Services erfolgreich eingerichtet!", "success")
            return redirect(url_for("overview.index"))
        except AimoError as exc:
            flash(str(exc), "error")

    return render_template("setup/first_boot.html", form=form)
