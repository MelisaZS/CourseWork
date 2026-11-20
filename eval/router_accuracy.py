"""Measures how often the router agent sends a question to the right source.

Every question in eval/router_questions.json (30 questions, 10 per source) is
given to agent.router.route(). The script prints the overall accuracy, the
accuracy per source and a confusion table (rows = expected, columns = predicted).

None of the questions are copied from the router's few-shot examples, so the
score shows how well the router handles questions it has not seen before.

Run with (Ollama must be running):
    python eval/router_accuracy.py
    python eval/router_accuracy.py --output eval/router_results.json   # also save as JSON
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Lets "python eval/router_accuracy.py" find config.py and the project packages
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

import config

ROUTES = ["db", "doc", "web"]
QUESTIONS_PATH = Path(__file__).with_name("router_questions.json")


def load_questions(path=QUESTIONS_PATH):
    """Read the test questions: [{"id", "question", "expected"}]."""
    with open(path, encoding="utf-8") as f:
        questions = json.load(f)
    for item in questions:
        if item["expected"] not in ROUTES:
            raise ValueError(f"Question {item['id']}: unknown route {item['expected']!r}")
    return questions


def check_ollama():
    """Return None if Ollama is running and has the model, otherwise an error message.

    route() quietly answers "doc" when Ollama is down, which would give a
    misleading 33% score. So we check before measuring anything.
    """
    url = f"{config.OLLAMA_URL.rstrip('/')}/api/tags"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        models = [m.get("name", "") for m in response.json().get("models", [])]
    except (requests.RequestException, ValueError):
        return f"Ollama'ya ulaşılamadı ({config.OLLAMA_URL}). Ollama'yı açıp tekrar deneyin."

    wanted = config.OLLAMA_MODEL
    if not any(name == wanted or name.split(":")[0] == wanted for name in models):
        return f"'{wanted}' modeli Ollama'da kurulu değil. Kurmak için: ollama pull {wanted}"
    return None


def evaluate(questions, route_fn=None, on_result=None):
    """Run every question through the router and collect the scores.

    route_fn defaults to agent.router.route; tests pass a fake one.
    on_result(index, item, predicted) is called after each question (for progress output).
    """
    if route_fn is None:
        from agent.router import route as route_fn  # imported here: loads the whole RAG/web stack

    confusion = {expected: {predicted: 0 for predicted in ROUTES} for expected in ROUTES}
    mistakes = []
    for index, item in enumerate(questions, start=1):
        predicted = route_fn(item["question"])
        if predicted not in ROUTES:
            raise ValueError(f"route() returned {predicted!r}, expected one of {ROUTES}")
        confusion[item["expected"]][predicted] += 1
        if predicted != item["expected"]:
            mistakes.append({**item, "predicted": predicted})
        if on_result:
            on_result(index, item, predicted)

    total = len(questions)
    correct = sum(confusion[r][r] for r in ROUTES)
    per_route = {}
    for r in ROUTES:
        route_total = sum(confusion[r].values())
        per_route[r] = {
            "total": route_total,
            "correct": confusion[r][r],
            "accuracy": round(100 * confusion[r][r] / route_total, 1) if route_total else 0.0,
        }
    return {
        "model": config.OLLAMA_MODEL,
        "total": total,
        "correct": correct,
        "accuracy": round(100 * correct / total, 1) if total else 0.0,
        "per_route": per_route,
        "confusion": confusion,
        "mistakes": mistakes,
    }


def format_report(result):
    """Turn the evaluate() result into the text printed on screen."""
    lines = [
        f"Router doğruluğu: {result['correct']}/{result['total']} = %{result['accuracy']}  (model: {result['model']})",
        "",
        "Kaynak bazında doğruluk:",
    ]
    for r in ROUTES:
        s = result["per_route"][r]
        lines.append(f"  {r:<4} {s['correct']:>2}/{s['total']:<2}  %{s['accuracy']}")

    lines += ["", "Karışıklık tablosu (satır = beklenen, sütun = router'ın kararı):"]
    lines.append("  " + " " * 10 + "".join(f"{r:>6}" for r in ROUTES))
    for expected in ROUTES:
        row = "".join(f"{result['confusion'][expected][p]:>6}" for p in ROUTES)
        lines.append(f"  {expected:<10}{row}")

    if result["mistakes"]:
        lines += ["", "Yanlış yönlendirilen sorular:"]
        for m in result["mistakes"]:
            lines.append(f"  #{m['id']:<3} beklenen {m['expected']:<4} -> {m['predicted']:<4} {m['question']}")
    return "\n".join(lines)


def print_progress(index, item, predicted):
    mark = "doğru" if predicted == item["expected"] else "YANLIŞ"
    print(f"[{index:>2}] {item['expected']:<4} -> {predicted:<4} {mark:<6} {item['question']}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Router doğruluk ölçümü")
    parser.add_argument("--output", help="sonuçları bu JSON dosyasına da yaz (örnek: eval/router_results.json)")
    args = parser.parse_args(argv)

    error = check_ollama()
    if error:
        print(error, file=sys.stderr)
        return 1

    questions = load_questions()
    print(f"{len(questions)} soru router'a soruluyor (model: {config.OLLAMA_MODEL})...\n", flush=True)
    result = evaluate(questions, on_result=print_progress)
    print("\n" + format_report(result))

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSonuçlar kaydedildi: {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
