
"""Flask web interface for document, database and web Q&A."""

from pathlib import Path

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.utils import secure_filename

import config
from agent.prompt_guard import is_suspicious
from agent.router import answer as router_answer
from agent.summarizer import get_cached_summary, summarize_pdf
from auth.admin import admin_dashboard
from auth.audit import log_event
from auth.decorators import current_user, is_safe_next, login_required, role_required
from auth.privacy import protect_response
from auth.users import UPLOAD_ROLES, allowed_routes, check_login
from rag.indexer import rebuild_index

app = Flask(__name__)
app.config.update(
    SECRET_KEY=config.SECRET_KEY,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.values.get("next", "")

    if request.method == "GET":
        if current_user():
            return redirect(url_for("index"))
        return render_template("login.html", next=next_url)

    username = request.form.get("username", "").strip()
    user = check_login(username, request.form.get("password", ""))

    if user is None:
        log_event(username or None, "login_failed", {"result": "denied"})
        return render_template(
            "login.html",
            error="Kullanıcı adı veya şifre hatalı.",
            username=username,
            next=next_url,
        ), 401

    session.clear()
    session["user"] = user
    log_event(user, "login_success", {"result": "success"})

    return redirect(
        next_url if is_safe_next(next_url) else url_for("index")
    )


@app.route("/logout", methods=["POST"])
def logout():
    user = current_user()
    if user:
        log_event(user, "logout", {"result": "success"})

    session.clear()
    return redirect(url_for("login"))


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    question = ""
    answer = None
    results = []
    error = None
    selected_route = None
    sources = []
    sql = None
    columns = []
    rows = []

    if request.method == "POST":
        question = request.form.get("question", "").strip()

        if not question:
            error = "Lütfen bir soru girin."
        elif is_suspicious(question):
            log_event(
                current_user(),
                "prompt_rejected",
                {"reason": "prompt_injection", "result": "denied"},
            )
            error = (
                "Sorunuz güvenlik kontrolü tarafından reddedildi. "
                "Lütfen sorunuzu yeniden düzenleyin."
            )
        else:
            try:
                user_role = current_user()["role"]

                response = router_answer(
                    question,
                    allowed_routes=allowed_routes(user_role),
                )

                # Apply role-based masking before rendering.
                response = protect_response(
                    response,
                    user_role,
                )
                log_event(
                    current_user(),
                    "question",
                    {
                        "route": response.get("route"),
                        "result": (
                            "denied"
                            if response.get("denied")
                            else "success"
                        ),
                    },
                )
                selected_route = response.get("route")
                answer = response.get("answer")
                results = response.get("matches") or []
                sources = response.get("sources") or []

                if selected_route == "db":
                    sql = response.get("sql") or ""
                    columns = response.get("columns") or []
                    rows = response.get("rows") or []

            except Exception:
                app.logger.exception("Soru yönlendirme başarısız")
                error = "Soru işlenirken bir hata oluştu."

    uploaded = request.args.get("uploaded", default=0, type=int)

    uploaded_pdfs = []

    for path in sorted(config.UPLOAD_DIR.glob("*.pdf")):
        try:
            summary = get_cached_summary(path)
        except (OSError, ValueError):
            app.logger.warning(
                "Kayıtlı özet okunamadı: %s",
                path.name,
            )
            summary = None

        uploaded_pdfs.append(
            {"name": path.name, "summary": summary}
        )

    return render_template(
        "index.html",
        question=question,
        answer=answer,
        results=results,
        error=error,
        uploaded=uploaded,
        route=selected_route,
        sources=sources,
        sql=sql,
        columns=columns,
        rows=rows,
        uploaded_pdfs=uploaded_pdfs,
    )


@app.route("/upload", methods=["POST"])
@role_required(*UPLOAD_ROLES)
def upload():
    files = request.files.getlist("files")

    if not files or any(not f.filename for f in files):
        log_event(
            current_user(),
            "upload_failed",
            {"result": "denied", "reason": "no_file_selected"},
        )
        return render_template(
            "index.html",
            question="",
            results=[],
            error="Lütfen PDF dosyası seçin.",
            uploaded=0,
        ), 400

    filenames = [
        secure_filename(f.filename)
        for f in files
    ]

    if any(
        not name.lower().endswith(".pdf")
        for name in filenames
    ):
        log_event(
            current_user(),
            "upload_failed",
            {"result": "denied", "reason": "invalid_file_type"},
        )
        return render_template(
            "index.html",
            question="",
            results=[],
            error="Yalnızca PDF dosyaları yüklenebilir.",
            uploaded=0,
        ), 400

    config.UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    saved_paths = []

    for file, filename in zip(files, filenames):
        destination = config.UPLOAD_DIR / filename
        counter = 1

        while destination.exists():
            name = Path(filename)
            destination = (
                config.UPLOAD_DIR
                / f"{name.stem}_{counter}{name.suffix}"
            )
            counter += 1

        file.save(destination)
        saved_paths.append(destination)

    try:
        rebuild_index()
    except Exception:
        app.logger.exception("PDF index güncellenemedi")
        log_event(
            current_user(),
            "upload_failed",
            {"result": "error", "reason": "index_failed"},
        )
        return render_template(
            "index.html",
            question="",
            results=[],
            error="Dosyalar kaydedildi ancak index güncellenemedi.",
            uploaded=0,
        ), 500

    for path in saved_paths:
        try:
            summarize_pdf(path)
        except Exception:
            app.logger.exception(
                "PDF özeti oluşturulamadı: %s",
                path.name,
            )
    log_event(
        current_user(),
        "upload_success",
        {"result": "success", "file_count": len(saved_paths)},
    )
    return redirect(
        url_for("index", uploaded=len(files))
    )


@app.route("/admin")
@role_required("admin")
def admin():
    """Security panel: audit log, rejected requests, users and daily question counts."""
    return render_template("admin.html", **admin_dashboard())


if __name__ == "__main__":
    app.run(debug=True)
