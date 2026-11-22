from flask import Blueprint, flash, redirect, render_template, request, url_for

from application.admin.forms import AdminPromptsForm
from application.auth.decorators import require_permission
from application.core_client import core_get, core_post, core_put
from application.ui_helpers import tr
from application.view_models import FunctionPermission, wrap_dto
from i18n import gettext_noop as _

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def index():
    return redirect(url_for("admin.users_list"))


@admin_bp.route("/prompts", methods=["GET", "POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def prompts_config():
    if request.method == "POST":
        form = AdminPromptsForm.from_request(request.form)
        status, payload = core_put(
            "/api/admin/prompts",
            json={
                "roleplay_prompt": form.roleplay_prompt,
                "memory_prompt": form.memory_prompt,
                "dialogue_author_prompt": form.dialogue_author_prompt,
                "diffuser_prompt": form.diffuser_prompt,
                "vision_persona_prompt": form.vision_persona_prompt,
            },
        )
        if status < 400:
            flash(tr(_("System prompts saved successfully.")), "success")
            return redirect(url_for("admin.prompts_config"))
        flash(payload.get("error") or tr(_("Failed to save prompts.")), "error")

    _, data = core_get("/api/admin/prompts")
    prompts_dto = wrap_dto(data.get("prompts", {}))
    return render_template(
        "admin/prompts.html",
        settings=wrap_dto({"prompts": prompts_dto}),
        prompts=prompts_dto,
        defaults=wrap_dto(data.get("defaults", {})),
        prompt_variants=data.get("prompt_variants", {}),
        default_prompt_variants=data.get("default_prompt_variants", {}),
        is_cloud_llm=bool(data.get("is_cloud_llm")),
        prompt_i18n=data.get("i18n", {}),
    )


@admin_bp.route("/backdrop", methods=["GET", "POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def backdrop_config():
    if request.method == "POST":
        if request.form.get("clear_backdrop"):
            status, payload = core_post("/api/admin/backdrop", json={"clear": True})
        else:
            file_obj = request.files.get("backdrop")
            if file_obj and file_obj.filename:
                status, payload = core_post(
                    "/api/admin/backdrop",
                    files={"backdrop": (file_obj.filename, file_obj.stream, file_obj.mimetype or "application/octet-stream")},
                )
            else:
                status, payload = 400, {"error": tr(_("Please select a backdrop image."))}
        if status < 400:
            flash(tr(_("System backdrop updated.")), "success")
        else:
            flash(payload.get("error") or tr(_("Failed to update backdrop.")), "error")
        return redirect(url_for("admin.backdrop_config"))

    _, data = core_get("/api/admin/backdrop")
    return render_template(
        "admin/backdrop.html",
        current_backdrop=data.get("default_backdrop_path"),
        settings=wrap_dto({"default_backdrop_path": data.get("default_backdrop_path")}),
        existing_locations_with_bg=wrap_dto(data.get("existing_locations_with_bg", [])),
    )


@admin_bp.route("/translations", methods=["GET"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def translations_config():
    _, status_data = core_get("/api/admin/translations/status")
    return render_template("admin/translations.html", worker_status=status_data)


from application.admin import services_views as _services_views  # noqa: E402, F401
from application.admin import users_views as _users_views  # noqa: E402, F401
