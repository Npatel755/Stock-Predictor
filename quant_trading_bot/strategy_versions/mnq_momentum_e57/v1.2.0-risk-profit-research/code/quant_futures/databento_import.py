"""Stream a user-provided Databento ZIP into contract/year Parquet partitions.

No paid API calls. The source archive stays untouched. A bounded decoder reads
DBN directly inside ZIP, so the 311MB compressed payload is not copied twice.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import zipfile
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from .config import file_hash, digest
from .data import canonical
from .contracts import expiration


def zip_store(archive, member):
    import databento as db
    from databento.common.dbnstore import DataSource

    class Source(DataSource):
        def __init__(self):
            pass

        @property
        def name(self):
            return member

        @property
        def nbytes(self):
            return archive.getinfo(member).file_size

        @property
        def reader(self):
            return archive.open(member)
    return db.DBNStore(Source())


def verify_archive(archive):
    manifest = json.loads(archive.read("manifest.json"))
    checked = []
    for item in manifest["files"]:
        name = item["filename"]
        if name not in archive.namelist() or archive.getinfo(name).file_size != item["size"]:
            raise ValueError(f"Archive member size mismatch: {name}")
        checksum = hashlib.sha256()
        with archive.open(name) as stream:
            for block in iter(lambda: stream.read(4*1024*1024), b""):
                checksum.update(block)
        expected = item["hash"].removeprefix("sha256:")
        if checksum.hexdigest() != expected:
            raise ValueError(f"Archive member checksum mismatch: {name}")
        checked.append(dict(filename=name, bytes=item["size"], sha256=expected))
    return manifest["job_id"], checked


def canonical_symbol(raw, observation_year):
    match = re.fullmatch(r"(MES|MNQ|ES|NQ)([HMUZ])(\d{1,2})", raw)
    if not match:
        return None
    root, month, tail = match.groups()
    if len(tail) == 2:
        year = 2000+int(tail)
    else:
        base = observation_year//10*10+int(tail)
        possible = [y for y in (base-10, base, base+10) if observation_year-1 <= y <= observation_year+5]
        if len(possible) != 1:
            raise ValueError(f"Ambiguous year for {raw} observed in {observation_year}")
        year = possible[0]
    return root, f"{root}{month}{year%100:02d}"


def normalize_chunk(frame):
    frame = frame.reset_index().rename(columns={"ts_event": "timestamp_utc", "symbol": "raw_symbol"})
    if "raw_symbol" not in frame:
        raise ValueError("Embedded raw symbology is required; do not infer instrument IDs")
    frame["timestamp_utc"] = pd.to_datetime(frame.timestamp_utc, utc=True)
    match = frame.raw_symbol.fillna("").str.fullmatch(r"(?:MES|MNQ|ES|NQ)[HMUZ]\d{1,2}")
    excluded = Counter(frame.loc[~match, "raw_symbol"].fillna("UNMAPPED").astype(str))
    b = frame.loc[match].copy()
    b["year"] = b.timestamp_utc.dt.year
    keys = b[["raw_symbol", "year"]].drop_duplicates()
    mapping = {(r.raw_symbol, r.year): canonical_symbol(r.raw_symbol, int(r.year)) for r in keys.itertuples(index=False)}
    roots, contracts = [], []
    for raw, year in zip(b.raw_symbol, b.year):
        root, contract = mapping[(raw, year)]
        roots.append(root)
        contracts.append(contract)
    b["instrument"], b["contract"] = roots, contracts
    b = canonical(b)
    prices = b[["open", "high", "low", "close"]]
    issues = {
        "invalid_price": ~np.isfinite(prices).all(axis=1) | (prices <= 0).any(axis=1),
        "invalid_ohlc": (b.high < prices.max(axis=1)) | (b.low > prices.min(axis=1)),
        "invalid_volume": ~np.isfinite(b.volume) | (b.volume < 0) | (b.volume % 1 != 0),
        "off_tick": ~np.isclose(prices/.25, np.round(prices/.25), rtol=0, atol=1e-6).all(axis=1),
        "duplicate": b.duplicated(["timestamp_utc", "contract"], keep=False),
        "timestamp_alignment": b.timestamp_utc.dt.floor("1min") != b.timestamp_utc,
        "prelaunch_micro": b.instrument.isin(["MES", "MNQ"]) & (b.timestamp_utc < pd.Timestamp("2019-05-05T22:00Z")),
    }
    flags = pd.Series("", index=b.index)
    for name, mask in issues.items():
        flags.loc[mask] += name+"|"
    flags.loc[b.volume == 0] += "zero_volume|"
    b["data_quality_flag"] = flags.str.rstrip("|")
    return b, excluded, {name: int(mask.sum()) for name, mask in issues.items()}


PARQUET_SCHEMA = pa.schema([
    ("timestamp_utc", pa.timestamp("ns", tz="UTC")), ("instrument", pa.string()),
    ("contract", pa.string()), ("raw_symbol", pa.string()), ("instrument_id", pa.uint32()),
    ("publisher_id", pa.uint16()), ("open", pa.float64()), ("high", pa.float64()),
    ("low", pa.float64()), ("close", pa.float64()), ("volume", pa.uint64()),
    ("bid", pa.float64()), ("ask", pa.float64()), ("bid_size", pa.float64()),
    ("ask_size", pa.float64()), ("quote_timestamp_utc", pa.timestamp("ns", tz="UTC")),
    ("session_id", pa.string()), ("is_roll_period", pa.bool_()), ("data_quality_flag", pa.string())])


def ingest_zip(source, output, chunk_rows=250000):
    from .research import json_write
    source, output = Path(source).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    writers, parts, coverage, by_contract = {}, [], {}, {}
    issues, excluded = Counter(), Counter()
    session_volume = defaultdict(int)
    last_times, total, source_rows = {}, 0, 0
    started = datetime.now(timezone.utc).isoformat()
    try:
        with zipfile.ZipFile(source) as archive:
            job, verified = verify_archive(archive)
            metadata = json.loads(archive.read("metadata.json"))
            if metadata["query"]["schema"] != "ohlcv-1m" or metadata["query"]["dataset"] != "GLBX.MDP3":
                raise ValueError("Expected GLBX.MDP3 one-minute export")
            for name in ("metadata.json", "condition.json"):
                (output/name).write_bytes(archive.read(name))
            json_write(output/"archive_verified.json", dict(job_id=job, source_zip=str(source), source_zip_sha256=file_hash(source), members=verified))
            member = next(x for x in archive.namelist() if x.endswith(".dbn.zst"))
            store = zip_store(archive, member)
            json_write(output/"symbology.json", json.loads(json.dumps(store.metadata.mappings, default=str)))
            for chunk, frame in enumerate(store.to_df(count=chunk_rows, map_symbols=True, pretty_ts=True)):
                source_rows += len(frame)
                bars, skipped, counts = normalize_chunk(frame)
                excluded.update(skipped)
                issues.update(counts)
                for contract, group in bars.groupby("contract", sort=False):
                    first, last = group.timestamp_utc.iloc[0], group.timestamp_utc.iloc[-1]
                    if contract in last_times and first <= last_times[contract]:
                        issues["cross_chunk_order_or_duplicate"] += 1
                    last_times[contract] = last
                    item = by_contract.setdefault(contract, dict(rows=0, first=str(first), last=str(last), instrument=group.instrument.iloc[0], instrument_ids=set()))
                    item["rows"] += len(group)
                    item["last"] = str(last)
                    item["instrument_ids"].update(map(int, group.instrument_id.unique()))
                vols = bars.groupby(["instrument", "session_id", "contract"], sort=False).volume.sum()
                for key, value in vols.items():
                    session_volume[key] += int(value)
                for (instrument, year), group in bars.groupby(["instrument", "year"], sort=False):
                    key = instrument, int(year)
                    if key not in writers:
                        path = output/"contracts"/instrument/f"{int(year)}.parquet"
                        path.parent.mkdir(parents=True, exist_ok=True)
                        writers[key] = pq.ParquetWriter(path, PARQUET_SCHEMA, compression="zstd", compression_level=6)
                        parts.append(path)
                    table = pa.Table.from_pandas(group[PARQUET_SCHEMA.names], schema=PARQUET_SCHEMA, preserve_index=False)
                    writers[key].write_table(table, row_group_size=100000)
                    item = coverage.setdefault(instrument, dict(rows=0, first=str(group.timestamp_utc.min()), last=str(group.timestamp_utc.max())))
                    item["rows"] += len(group)
                    item["last"] = str(group.timestamp_utc.max())
                total += len(bars)
                if chunk % 10 == 0:
                    print(f"Imported {source_rows:,} source rows; {total:,} outright bars; through {frame.index.max()}", flush=True)
            for writer in writers.values():
                writer.close()
            writers.clear()
            volume_rows = [dict(instrument=i, session_id=s, contract=c, volume=v) for (i, s, c), v in session_volume.items()]
            pd.DataFrame(volume_rows).to_parquet(output/"session_volumes.parquet", index=False)
            contract_rows = {k: {**v, "instrument_ids": sorted(v["instrument_ids"])} for k, v in by_contract.items()}
            json_write(output/"contracts.json", contract_rows)
            files = [dict(path=str(p.relative_to(output)), bytes=p.stat().st_size, sha256=file_hash(p)) for p in sorted(parts)]
            report = dict(job_id=job, status="validated" if not sum(issues.values()) else "quality_review_required",
                source_zip=str(source), started_at=started, completed_at=datetime.now(timezone.utc).isoformat(),
                source_rows=source_rows, outright_rows=total, excluded_non_outright_rows=sum(excluded.values()),
                excluded_symbols=dict(excluded), quality_issues=dict(issues), coverage=coverage,
                raw_contract_prices=True, synthetic=False, bid_ask_available=False,
                license_note="User-provided Databento export; user entitlement governs private use and redistribution. No paid API call made.",
                files=files, dataset_version=digest(files),
                price_units="Databento fixed 1e-9 prices decoded by official SDK to index points",
                notes=["All raw outright contracts retained; spread rows remain in the original source ZIP and are counted, not relabeled.",
                       "ES/NQ are distinct mini futures; micro histories are not invented before their actual observations.",
                       "No missing bar, bid or ask is fabricated; zero-volume and quality flags remain explicit."])
            json_write(output/"import_report.json", report)
            return report
    except BaseException as error:
        for writer in writers.values():
            writer.close()
        json_write(output/"FAILED.json", dict(error=repr(error), source_rows=source_rows, outright_rows=total, completed=False))
        raise
