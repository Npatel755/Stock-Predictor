"""Physical, chronological train/validation/test partitions with a sealed test boundary."""
from datetime import datetime, timezone
from pathlib import Path
import json
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from .config import digest, file_hash


def partition_catalog(catalog_path, train_end="2024-01-01T00:00:00Z", test_start="2026-01-01T00:00:00Z", retire_unsplit=True):
    from .research import json_write
    catalog_path = Path(catalog_path).resolve()
    catalog = json.loads(catalog_path.read_text())
    train_end, test_start = pd.Timestamp(train_end), pd.Timestamp(test_start)
    if train_end.tzinfo is None or test_start.tzinfo is None or train_end >= test_start:
        raise ValueError("Ordered timezone-aware split boundaries required")
    protocol = dict(source_job=catalog["active_job"], source_dataset_version=catalog["dataset_version"],
        training_end_exclusive=str(train_end), validation_start_inclusive=str(train_end),
        validation_end_exclusive=str(test_start), test_start_inclusive=str(test_start),
        method="chronological calendar boundaries; never random shuffle",
        test_policy="excluded from fitting, calibration, feature selection and hyperparameter/model selection",
        created_at=datetime.now(timezone.utc).isoformat())
    protocol_id = digest({k: v for k, v in protocol.items() if k != "created_at"})
    protocol["protocol_id"] = protocol_id
    protocol_file = catalog_path.parent/"manifests"/f"split_protocol_{protocol_id}.json"
    protocol_file.parent.mkdir(parents=True, exist_ok=True)
    if protocol_file.exists():
        existing = json.loads(protocol_file.read_text())
        if existing["protocol_id"] != protocol_id:
            raise ValueError("Split protocol changed")
        protocol = existing
    else:
        with open(protocol_file, "x", encoding="utf-8") as f:
            json.dump(protocol, f, indent=2)
    updated = json.loads(json.dumps(catalog))
    for instrument, item in catalog["instruments"].items():
        if item.get("split_protocol_id") == protocol_id:
            for part in item["splits"].values():
                if file_hash(part["path"]) != part["dataset_version"]:
                    raise ValueError("Existing partition hash mismatch")
            continue
        source = Path(item["path"])
        if source.suffix != ".parquet" or file_hash(source) != item["dataset_version"]:
            raise ValueError("Unsplit source provenance mismatch")
        directory = source.parent.parent/"splits"/instrument
        directory.mkdir(parents=True, exist_ok=False)
        parquet = pq.ParquetFile(source)
        writers, counts, first, last, paths = {}, {}, {}, {}, {}
        for role in ("train", "validation", "test"):
            path = directory/f"{role}.parquet"
            paths[role] = path
            writers[role] = pq.ParquetWriter(path, parquet.schema_arrow, compression="zstd", compression_level=6)
            counts[role] = 0
        try:
            for batch in parquet.iter_batches(batch_size=100000):
                table = pa.Table.from_batches([batch])
                ts = table.column("timestamp_utc")
                left = pa.scalar(train_end.to_pydatetime(), type=ts.type)
                right = pa.scalar(test_start.to_pydatetime(), type=ts.type)
                masks = {"train": pc.less(ts, left),
                         "validation": pc.and_(pc.greater_equal(ts, left), pc.less(ts, right)),
                         "test": pc.greater_equal(ts, right)}
                for role, mask in masks.items():
                    part = table.filter(mask)
                    if not len(part):
                        continue
                    writers[role].write_table(part, row_group_size=100000)
                    counts[role] += len(part)
                    first.setdefault(role, str(part.column("timestamp_utc")[0].as_py()))
                    last[role] = str(part.column("timestamp_utc")[-1].as_py())
        finally:
            for writer in writers.values():
                writer.close()
        if sum(counts.values()) != parquet.metadata.num_rows or any(count == 0 for count in counts.values()):
            raise ValueError("Split lost rows or produced an empty research period")
        if not (pd.Timestamp(last["train"]) < pd.Timestamp(first["validation"]) and pd.Timestamp(last["validation"]) < pd.Timestamp(first["test"])):
            raise ValueError("Split date boundaries overlap")
        parts = {}
        for role, path in paths.items():
            manifest = dict(dataset_version=file_hash(path), source_dataset_version=item["dataset_version"],
                source_job_id=catalog["active_job"], synthetic=catalog.get("synthetic", False), raw_contract_prices=True,
                provider=item["provider"], license_note=item["license_note"], timestamp_semantics="bar_open",
                instrument=instrument, split_role=role, split_protocol_id=protocol_id,
                train_end_exclusive=str(train_end), test_start_inclusive=str(test_start),
                coverage=dict(rows=counts[role], start=first[role], end=last[role]),
                model_selection_access=role != "test")
            json_write(path.with_suffix(".manifest.json"), manifest)
            parts[role] = dict(path=str(path), **manifest)
        development = directory/"development.dataset.json"
        descriptor = dict(kind="partitioned_development", dataset_version=digest([parts[x]["dataset_version"] for x in ("train", "validation")]),
            provider=item["provider"], license_note=item["license_note"], instrument=instrument,
            source_job_id=catalog["active_job"], synthetic=catalog.get("synthetic", False), raw_contract_prices=True, timestamp_semantics="bar_open",
            split_role="development", split_protocol_id=protocol_id, train_end_exclusive=str(train_end),
            test_start_inclusive=str(test_start), files=[parts[x]["path"] for x in ("train", "validation")],
            file_hashes={parts[x]["path"]: parts[x]["dataset_version"] for x in ("train", "validation")},
            test_partition=parts["test"], coverage=dict(rows=counts["train"]+counts["validation"], start=first["train"], end=last["validation"]))
        json_write(development, descriptor)
        updated["instruments"][instrument].update(path=str(development), dataset_version=descriptor["dataset_version"],
            unsplit_dataset_version=item["dataset_version"], split_protocol_id=protocol_id, splits=parts)
        # Commit the per-instrument descriptor before retiring only its verified,
        # superseded derived file. The original ZIP and raw contract partitions remain.
        json_write(catalog_path, updated)
        json_write(Path(updated["active_root"])/"selected_datasets.json", updated["instruments"])
        parquet.close()
        if retire_unsplit:
            source.unlink()
            source.with_suffix(".manifest.json").unlink()
        print(f"{instrument}: train={counts['train']:,}; validation={counts['validation']:,}; test={counts['test']:,}", flush=True)
    updated["split_protocol"] = protocol
    json_write(catalog_path, updated)
    json_write(Path(updated["active_root"])/"selected_datasets.json", updated["instruments"])
    return updated
