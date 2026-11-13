
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

import config
from rag.answer import answer_from_docs
from rag.indexer import rebuild_index

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index():
    question = ""
    answer = None
    results = []
    error = None

    if request.method == "POST":
        question = request.form.get("question", "").strip()

        if not question:
            error = "Lütfen bir soru girin."
        else:
            try:
                result = answer_from_docs(question, include_matches=True)
                answer = result["answer"]
                results = result.get("matches", [])
            except Exception:
                app.logger.exception("PDF cevabı üretilemedi")
                error = "Cevap üretilemedi. PDF indeksini kontrol edin."

    uploaded = request.args.get("uploaded", default=0, type=int)
    return render_template(
        "index.html",
        question=question,
        answer=answer,
        results=results,
        error=error,
        uploaded=uploaded,
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

        # Aynı isimde dosya varsa eskisinin üzerine yazma.
        counter = 1
        while destination.exists():
            name = Path(filename)
            destination = config.UPLOAD_DIR / f"{name.stem}_{counter}{name.suffix}"
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
