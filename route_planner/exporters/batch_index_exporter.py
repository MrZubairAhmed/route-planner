from pathlib import Path

from ..models import BatchItemResult


def write_batch_index(items: list[BatchItemResult], output_path: Path) -> Path:
    succeeded = [i for i in items if i.planned is not None]
    failed = [i for i in items if i.error]
    total_schools = sum(i.stop_count for i in succeeded)
    total_km = sum(i.planned.total_distance_km for i in succeeded if i.planned)

    cards = []
    for item in items:
        if item.error:
            cards.append(
                f"""
            <div class="card error">
              <h3>{_esc(item.name)}</h3>
              <p class="status">Failed: {_esc(item.error)}</p>
            </div>"""
            )
            continue

        planned = item.planned
        assert planned is not None
        route_links = "".join(
            f'<a class="btn" href="{_esc(c.google_maps_url)}" target="_blank">'
            f'{"Open Routes" if len(planned.chunks) == 1 else f"Open Routes {c.route_no}"}</a>'
            for c in planned.chunks
        )
        cards.append(
            f"""
            <div class="card">
              <h3>{_esc(item.name)}</h3>
              <p>{item.stop_count} locations</p>
              <div class="actions">{route_links}</div>
            </div>"""
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Excel Routes</title>
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 24px; }}
    .header {{ background: #fff; padding: 24px; border-radius: 12px; margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    h1 {{ margin: 0 0 8px; }}
    .stats {{ color: #555; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }}
    .card {{ background: #fff; border-radius: 10px; padding: 18px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }}
    .card.error {{ border-left: 4px solid #ea4335; }}
    .card h3 {{ margin: 0 0 8px; font-size: 1.05rem; }}
    .card p {{ margin: 0 0 12px; color: #666; font-size: 0.9rem; }}
    .actions {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .btn {{ display: inline-block; padding: 8px 14px; background: #4285F4; color: #fff; text-decoration: none; border-radius: 6px; font-size: 0.85rem; }}
    .btn.small {{ background: #34A853; padding: 6px 10px; font-size: 0.8rem; }}
    .status {{ color: #c5221f; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>Excel Routes</h1>
    <p class="stats">
      {len(succeeded)} batches completed · {len(failed)} failed ·
      {total_schools} total locations
    </p>
  </div>
  <div class="grid">
    {"".join(cards)}
  </div>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    return output_path


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
