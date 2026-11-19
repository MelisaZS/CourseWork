
"""Flask web interface for document, database and web Q&A."""

from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

import config
from agent.router import answer as router_answer
from rag.indexer import rebuild_index

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    question = ""
    answer = None
    results = []
    error = None
    selected_route = None
    sources = []
    sql = ""
    columns = []
    rows = []

    if request.method == "POST":
        question = request.form.get("question", "").strip()

        if not question:
            error = "Lütfen bir soru girin."
        else:
            try:
                response = router_answer(question)

                answer = response.get("answer")
                results = response.get("matches", [])
                selected_route = response.get("route")
                sources = response.get("sources", [])
                sql = response.get("sql", "")
                columns = response.get("columns", [])
                rows = response.get("rows", [])

            except Exception:
                app.logger.exception("Soru yönlendirme başarısız")
                error = "Soru işlenirken bir hata oluştu."

    uploaded = request.args.get("uploaded", default=0, type=int)

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
    )


@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")

    if not files or any(not f.filename for f in files):
        return render_template(
            "index.html",
            question="",
            results=[],
            error="Lütfen PDF dosyası seçin.",
            uploaded=0,
        ), 400

    filenames = [secure_filename(f.filename) for f in files]

    if any(not name.lower().endswith(".pdf") for name in filenames):
        return render_template(
            "index.html",
            question="",
            results=[],
            error="Yalnızca PDF dosyaları yüklenebilir.",
            uploaded=0,
        ), 400

    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    for file, filename in zip(files, filenames):
        destination = config.UPLOAD_DIR / filename

        # Prevent overwriting files with the same name.
        counter = 1

        while destination.exists():
            name = Path(filename)
            destination = (
                config.UPLOAD_DIR
                / f"{name.stem}_{counter}{name.suffix}"
            )
            counter += 1

        file.save(destination)

    try:
        rebuild_index()
    except Exception:
        app.logger.exception("PDF index güncellenemedi")
        return render_template(
            "index.html",
            question="",
            results=[],
            error="Dosyalar kaydedildi ancak index güncellenemedi.",
            uploaded=0,
        ), 500

    return redirect(url_for("index", uploaded=len(files)))


if __name__ == "__main__":
    app.run(debug=True)
