"""Flask web UI — upload Excel, get optimized routes automatically."""

import logging
import shutil
import uuid
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, send_file, send_from_directory, url_for

from route_planner.config import PlannerConfig
from route_planner.excel_format import analyze_excel
from route_planner.process import process_excel
from route_planner.template import write_format_template

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
JOBS_DIR = APP_DIR / "web_jobs"
JOBS_DIR.mkdir(exist_ok=True)
TEMPLATE_PATH = APP_DIR / "route_template.xlsx"

app = Flask(__name__, template_folder=str(APP_DIR / "templates"))
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/template")
def download_template():
    write_format_template(TEMPLATE_PATH)
    return send_file(TEMPLATE_PATH, as_attachment=True, download_name="route_planner_template.xlsx")


def _save_upload(file) -> tuple[str, Path]:
    job_id = str(uuid.uuid4())[:8]
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True)
    input_path = job_dir / "input.xlsx"
    file.save(input_path)
    return job_id, input_path


@app.route("/api/preview", methods=["POST"])
def preview():
    """Analyze uploaded Excel and return detected format + recommended settings."""
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "No file uploaded"}), 400

    job_id, input_path = _save_upload(file)

    try:
        _, profile = analyze_excel(str(input_path))
        return jsonify(
            {
                "job_id": job_id,
                "rows": profile.row_count,
                "destinations": profile.destination_count,
                "has_start": profile.has_start,
                "start_lat": profile.start_lat,
                "start_lng": profile.start_lng,
                "districts": profile.districts,
                "tehsils": profile.tehsils,
                "district_count": profile.district_count,
                "tehsil_count": profile.tehsil_count,
                "recommended_batch_by": profile.recommended_batch_by,
                "recommended_skip_geometry": profile.recommended_skip_geometry,
                "warnings": profile.warnings,
                "summary": profile.summary(),
            }
        )
    except Exception as exc:
        shutil.rmtree(JOBS_DIR / job_id, ignore_errors=True)
        return jsonify({"error": str(exc)}), 400


@app.route("/api/process", methods=["POST"])
def process_upload():
    """One-step: upload Excel and generate routes using auto-detected settings."""
    file = request.files.get("file")
    job_id = request.form.get("job_id", "").strip()

    if file and file.filename:
        job_id, input_path = _save_upload(file)
    elif job_id:
        input_path = JOBS_DIR / job_id / "input.xlsx"
        if not input_path.exists():
            return jsonify({"error": "Upload expired. Please upload again."}), 400
    else:
        return jsonify({"error": "No file uploaded"}), 400

    return _run_process(job_id, input_path, wants_json=True)


@app.route("/plan", methods=["POST"])
def plan():
    job_id = request.form.get("job_id", "").strip()
    if not job_id:
        return redirect(url_for("index"))

    input_path = JOBS_DIR / job_id / "input.xlsx"
    if not input_path.exists():
        return render_template("error.html", message="Upload expired. Please upload again.")

    return _run_process(job_id, input_path, wants_json=False)


def _run_process(job_id: str, input_path: Path, wants_json: bool):
    output_dir = JOBS_DIR / job_id / "output"
    batch_by = request.form.get("batch_by", "auto")
    optimizer = request.form.get("optimizer", "ortools")
    max_waypoints = int(request.form.get("max_waypoints", 23))
    max_stops = int(request.form.get("max_stops_per_batch", 150))
    skip_geometry = request.form.get("skip_geometry") == "on"

    start_lat = request.form.get("start_lat", "").strip()
    start_lng = request.form.get("start_lng", "").strip()
    group_filter = request.form.get("group_filter", "").strip()
    filters = [x.strip() for x in group_filter.split(",") if x.strip()] or None

    config = PlannerConfig(
        max_waypoints_per_url=max_waypoints,
        optimizer=optimizer,
        max_stops_per_batch=max_stops,
        skip_geometry=skip_geometry,
    )

    try:
        result = process_excel(
            str(input_path),
            output_dir,
            config=config,
            batch_by=batch_by,
            start_lat=float(start_lat) if start_lat else None,
            start_lng=float(start_lng) if start_lng else None,
            group_filter=filters,
        )

        if wants_json:
            return jsonify(_result_payload(job_id, result))

        if result.mode == "batch":
            return render_template("results_batch.html", job_id=job_id, result=result.batch, profile=result.profile)
        return render_template(
            "results_single.html",
            job_id=job_id,
            planned=result.single,
            paths=result.output_paths,
            profile=result.profile,
        )
    except Exception as exc:
        logger.exception("Planning failed")
        if wants_json:
            return jsonify({"error": str(exc)}), 400
        return render_template("error.html", message=str(exc))


def _result_payload(job_id: str, result) -> dict:
    payload = {
        "job_id": job_id,
        "mode": result.mode,
        "batch_by": result.batch_by,
        "destinations": result.destination_count,
        "total_distance_km": round(result.total_distance_km, 1),
        "summary": result.profile.summary(),
    }
    if result.mode == "batch" and result.batch:
        payload["index_url"] = url_for("serve_file", job_id=job_id, filename="batch_index.html")
        payload["batches"] = [
            {
                "name": item.name,
                "locations": item.stop_count,
                "distance_km": round(item.planned.total_distance_km, 1) if item.planned else 0,
                "map_url": url_for("serve_file", job_id=job_id, filename=f"{item.output_dir.name}/{item.map_html}")
                if item.output_dir and item.map_html
                else None,
                "error": item.error,
            }
            for item in result.batch.items
        ]
    elif result.single and result.output_paths:
        payload["map_url"] = url_for("serve_file", job_id=job_id, filename="route_map.html")
        payload["excel_url"] = url_for("serve_file", job_id=job_id, filename="optimized_route.xlsx")
        payload["google_maps_urls"] = [c.google_maps_url for c in result.single.chunks]
    return payload


@app.route("/files/<job_id>/<path:filename>")
def serve_file(job_id: str, filename: str):
    directory = JOBS_DIR / job_id / "output"
    return send_from_directory(directory, filename)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print("Route Planner")
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
