from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def build_report(items: list[dict[str, Any]], dry_run: bool, destination: str = "apple") -> dict[str, Any]:
    summary = Counter(str(item["status"]) for item in items)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "destination": destination,
        "summary": dict(sorted(summary.items())),
        "items": items,
    }


def write_reports(report: dict[str, Any], report_dir: str | Path) -> dict[str, Path]:
    output_dir = Path(report_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = str(report.get("destination") or "apple")
    prefix = "" if destination == "apple" else f"{destination}-"
    main_name = f"{prefix}dry-run.json" if report.get("dry_run") else f"{prefix}transfer.json"
    main_path = output_dir / main_name
    main_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    unmatched_path = output_dir / f"{prefix}unmatched.csv"
    ambiguous_path = output_dir / f"{prefix}ambiguous.csv"
    _write_status_csv(unmatched_path, report["items"], {"not_found", "rejected", "failed", "duplicate_match"})
    _write_status_csv(ambiguous_path, report["items"], {"ambiguous"})

    return {
        "main": main_path,
        "unmatched": unmatched_path,
        "ambiguous": ambiguous_path,
    }


def load_latest_report(report_dir: str | Path, destination: str = "apple") -> tuple[Path, dict[str, Any]]:
    output_dir = Path(report_dir)
    prefix = "" if destination == "apple" else f"{destination}-"
    candidates = [output_dir / f"{prefix}transfer.json", output_dir / f"{prefix}dry-run.json"]
    existing = [path for path in candidates if path.exists()]
    if not existing:
        raise FileNotFoundError(f"В папке {output_dir} нет файлов отчетов")
    latest = max(existing, key=lambda path: path.stat().st_mtime)
    return latest, json.loads(latest.read_text(encoding="utf-8"))


def _write_status_csv(path: Path, items: list[dict[str, Any]], statuses: set[str]) -> None:
    rows = [item for item in items if item.get("status") in statuses]
    fields = [
        "status",
        "reason",
        "score",
        "source_title",
        "source_artists",
        "source_album",
        "destination_title",
        "destination_artist",
        "destination_album",
        "destination_url",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for item in rows:
            source = item.get("source") or {}
            destination = item.get("destination") or item.get("apple") or {}
            writer.writerow(
                {
                    "status": item.get("status", ""),
                    "reason": item.get("reason", ""),
                    "score": item.get("score", ""),
                    "source_title": source.get("title", ""),
                    "source_artists": ", ".join(source.get("artists", [])),
                    "source_album": source.get("album", ""),
                    "destination_title": destination.get("title", ""),
                    "destination_artist": destination.get("artist", ""),
                    "destination_album": destination.get("album", ""),
                    "destination_url": destination.get("url", ""),
                }
            )
