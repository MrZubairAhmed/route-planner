"""Generic entry point: upload Excel → get optimized routes."""

from dataclasses import dataclass, replace
from pathlib import Path

from .config import PlannerConfig
from .excel_format import ExcelProfile, analyze_excel, resolve_batch_mode
from .models import BatchPlanResult, PlannedRoute
from .planner import plan_batch, plan_route, write_all_outputs


@dataclass
class ProcessResult:
    """Result of processing any compatible Excel file."""

    profile: ExcelProfile
    mode: str  # single | batch
    batch_by: str
    single: PlannedRoute | None = None
    batch: BatchPlanResult | None = None
    output_dir: Path | None = None
    output_paths: dict[str, Path] | None = None

    @property
    def destination_count(self) -> int:
        if self.mode == "batch" and self.batch:
            return self.batch.total_schools
        if self.single:
            return len(self.single.ordered_stops)
        return self.profile.destination_count

    @property
    def total_distance_km(self) -> float:
        if self.mode == "batch" and self.batch:
            return self.batch.total_distance_km
        if self.single:
            return self.single.total_distance_km
        return 0.0


def process_excel(
    input_path: str,
    output_dir: str | Path,
    config: PlannerConfig | None = None,
    batch_by: str = "auto",
    start_lat: float | None = None,
    start_lng: float | None = None,
    start_name: str = "Start",
    group_filter: list[str] | None = None,
) -> ProcessResult:
    """
    Process any Excel file in the standard format and write route outputs.

    Automatically detects start point, destination columns, and whether to
    batch by District or Tehsil when batch_by='auto' (default).
    """
    config = config or PlannerConfig()
    _, profile = analyze_excel(input_path)

    if profile.recommended_skip_geometry and not config.skip_geometry:
        config = replace(config, skip_geometry=True)

    resolved_batch = resolve_batch_mode(profile, batch_by)
    output_path = Path(output_dir)

    kwargs = {
        "start_lat": start_lat or profile.start_lat,
        "start_lng": start_lng or profile.start_lng,
        "start_name": start_name,
    }

    if resolved_batch != "none":
        batch_result = plan_batch(
            input_path,
            output_path,
            config=config,
            group_by=resolved_batch,
            district_filter=group_filter,
            **kwargs,
        )
        return ProcessResult(
            profile=profile,
            mode="batch",
            batch_by=resolved_batch,
            batch=batch_result,
            output_dir=output_path,
            output_paths={
                "index": batch_result.index_html,
                "excel": batch_result.master_excel,
            },
        )

    planned = plan_route(input_path, config=config, **kwargs)
    paths = write_all_outputs(planned, output_path)
    return ProcessResult(
        profile=profile,
        mode="single",
        batch_by="none",
        single=planned,
        output_dir=output_path,
        output_paths=paths,
    )
