"""Print aggregate scanner results without names, SQL text or file paths."""

import argparse
import json
from collections import Counter
from pathlib import Path

from src.monitor.scanners.sql_scanner import SQLScanner
from src.pipeline.sql_pipeline import SQLPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--allowed-root", type=Path, required=True)
    args = parser.parse_args()
    run = SQLPipeline(SQLScanner(allowed_root=args.allowed_root)).run_directory(args.directory)
    print(json.dumps({
        "status": run.status,
        "files": len(run.processed_files),
        "entities": run.metrics.entity_count if run.metrics else 0,
        "assets": len(run.guardian_objects),
        "findings": len(run.evidence),
        "parse_errors": run.parse_error_count,
        "warnings": run.warning_count,
        "rule_counts": dict(sorted(Counter(item.rule_id for item in run.evidence).items())),
        "severity_counts": dict(sorted(
            Counter(item.severity.value for item in run.evidence).items()
        )),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
