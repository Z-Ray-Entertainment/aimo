from flask import flash, redirect, render_template, request, url_for

from application.admin.forms import AdminServicesForm
from application.admin.views import admin_bp
from application.auth.decorators import require_permission
from application.core_client import core_get, core_put
from application.ui_helpers import mask_secret, tr
from application.view_models import FunctionPermission, wrap_dto
from i18n import gettext_noop as _


@admin_bp.route("/services", methods=["GET", "POST"])
@require_permission(FunctionPermission.ADMIN_ACCESS)
def services_config():
    if request.method == "POST":
        form = AdminServicesForm.from_request(request.form)
        status, payload = core_put(
            "/api/admin/services",
            json={
                "llm_backend": form.llm_backend,
                "llm_configs": {
                    "ollama": {"base_url": form.ollama_url},
                    "google_ai": {"api_key": form.google_ai_api_key},
                },
                "image_gen_backend": form.image_gen_backend,
                "image_gen_configs": {
                    "comfyui": {"base_url": form.comfyui_url},
                    "google_ai": {"model": form.google_ai_image_model},
                },
                "search_backend": form.search_backend,
                "search_configs": {"searxng": {"base_url": form.searxng_url}},
                "tasks": {
                    "roleplay_model": form.roleplay_model,
                    "memory_model": form.memory_model,
                    "assistant_model": form.assistant_model,
                    "vision_model": form.vision_model,
                    "classification_model": form.classification_model,
                },
                "params": {
                    "num_ctx": form.num_ctx,
                    "temperature": form.temperature,
                    "top_p": form.top_p,
                    "repeat_penalty": form.repeat_penalty,
                    "max_tokens": form.max_tokens,
                },
            },
        )
        if status < 400:
            flash(tr(_("Service settings and models saved successfully.")), "success")
            return redirect(url_for("admin.services_config"))
        flash(payload.get("error") or tr(_("Failed to save service settings.")), "error")

    _, cfg = core_get("/api/admin/services")
    _, health = core_get("/api/admin/health")
    _, models_data = core_get("/api/admin/models")

    llm_cfgs = cfg.get("llm_configs", {})
    img_cfgs = cfg.get("image_gen_configs", {})
    search_cfgs = cfg.get("search_configs", {})
    google_key = llm_cfgs.get("google_ai", {}).get("api_key", "")
    rec_google_img = cfg.get("recommended_google_image_model") or "gemini-3.1-flash-image-preview"

    return render_template(
        "admin/services.html",
        settings=wrap_dto(cfg),
        ollama_url=llm_cfgs.get("ollama", {}).get("base_url", "http://localhost:11434"),
        comfyui_url=img_cfgs.get("comfyui", {}).get("base_url", "http://localhost:8188"),
        searxng_url=search_cfgs.get("searxng", {}).get("base_url", "http://localhost:8080"),
        google_ai_image_model=img_cfgs.get("google_ai", {}).get("model", rec_google_img),
        installed_models=models_data.get("models", []),
        available_image_models=models_data.get("image_models", []),
        ollama_grouped_recommended=wrap_dto(cfg.get("ollama_grouped_recommended", [])),
        ollama_unique_models=cfg.get("ollama_unique_models", []),
        google_recommended_models=cfg.get("google_recommended_models", {}),
        recommended_by_backend=cfg.get("recommended_by_backend", {}),
        recommended_google_image_model=rec_google_img,
        llm_healthy=bool(health.get("llm_healthy")),
        ollama_healthy=bool(health.get("llm_healthy") and cfg.get("llm_backend") == "ollama"),
        comfy_healthy=bool(health.get("image_gen_healthy") and cfg.get("image_gen_backend") == "comfyui"),
        image_gen_healthy=bool(health.get("image_gen_healthy")),
        has_google_api_key=bool(google_key),
        has_google_ai_api_key=bool(google_key),
        google_api_key_hint=mask_secret(google_key),
        google_ai_api_key_hint=mask_secret(google_key),
    )
