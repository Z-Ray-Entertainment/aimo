from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

from application.core_client import core_get, core_post
from application.setup.forms import FirstBootForm
from application.ui_helpers import mask_secret
from i18n import normalize_language

setup_bp = Blueprint("setup", __name__, url_prefix="/setup")


@setup_bp.route("", methods=["GET", "POST"])
def first_boot():
    code, status_data = core_get("/api/setup/status")
    if code == 200 and not status_data.get("first_boot_required"):
        return redirect(url_for("auth.login"))

    form = FirstBootForm.from_request(request.form if request.method == "POST" else {})
    if request.method == "POST":
        if not form.language:
            form.language = normalize_language(request.accept_languages.best_match(["en", "de"]))
        payload = {
            "username": form.username,
            "email": form.email,
            "password": form.password,
            "language": form.language,
            "persona_name": form.persona_name,
            "persona_gender": form.persona_gender,
            "persona_description": form.persona_description,
            "persona_appearance": form.persona_appearance,
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
            "apply_recommended_models": bool(form.apply_recommended_models),
            "roleplay_model": form.roleplay_model,
            "memory_model": form.memory_model,
            "utility_model": form.utility_model,
            "vision_model": form.vision_model,
            "classification_model": form.classification_model,
        }
        res_code, res_data = core_post("/api/setup/first-boot", json=payload)
        if res_code < 400:
            flash("System initialized. Please log in.", "success")
            return redirect(url_for("auth.login"))
        flash(res_data.get("error") or "Setup failed.", "error")

    return _render_first_boot(form, status_data)


@setup_bp.route("/verify-backend", methods=["POST"])
def verify_backend():
    _, status_data = core_get("/api/setup/status")
    if not status_data.get("first_boot_required"):
        abort(404)

    data = request.get_json(silent=True) or request.form.to_dict()
    raw_backend = str(data.get("llm_backend") or "ollama").strip().lower()
    submitted_cfg = {
        "base_url": str(data.get("ollama_url") or data.get("base_url") or "").strip(),
        "api_key": str(data.get("google_ai_api_key") or data.get("api_key") or "").strip(),
    }
    status_code, payload = core_post(
        "/api/setup/verify-backend",
        json={"llm_backend": raw_backend, "config": submitted_cfg},
    )
    return jsonify(payload), status_code


def _render_first_boot(form: FirstBootForm, status_data: dict):
    providers = {p["id"]: p for p in status_data.get("llm_providers", [])}
    recommended_by_backend = {
        pid: p.get("recommended_tasks", {}) for pid, p in providers.items()
    }
    return render_template(
        "setup/first_boot.html",
        form=form,
        has_env_google_key=False,
        env_google_key_hint=mask_secret(""),
        ollama_recommended=[],
        google_recommended=[],
        recommended_by_backend=recommended_by_backend,
        recommended_google_image_model="gemini-3.1-flash-image-preview",
        ollama_unique_models=[],
    )
