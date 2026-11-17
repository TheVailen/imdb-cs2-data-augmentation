"""Prepare unchanged CS2 screenshots and a source manifest for two annotators."""

import argparse
import csv
import hashlib
import re
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image


PROJECT = Path(__file__).resolve().parents[1]
SOURCE_URL = (
    "https://www.hltv.org/matches/2400208/"
    "spirit-vs-furia-blast-rivals-2026-season-2"
)
DEMOS = {
    "Ancient": "spirit-vs-furia-m1-ancient.dem",
    "Dust2": "spirit-vs-furia-m2-dust2.dem",
    "Mirage": "spirit-vs-furia-m3-mirage.dem",
}
PATTERN = re.compile(r"CS2-(\d+)\s+(\d+)-(\d+)\.jpg", re.IGNORECASE)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    records = []
    hashes = set()

    # Validate all input metadata and image files before creating outputs.
    for map_name, demo_name in DEMOS.items():
        demos = list(source.rglob(demo_name))
        if len(demos) != 1:
            raise ValueError(f"Expected exactly one demo: {demo_name}")
        for image in sorted((source / map_name).glob("*.jpg")):
            match = PATTERN.fullmatch(image.name)
            if not match:
                raise ValueError(f"Unexpected filename: {image.name}")
            _, minutes, seconds = map(int, match.groups())
            if seconds >= 60:
                raise ValueError(f"Invalid timestamp: {image.name}")
            elapsed = minutes * 60 + seconds
            timestamp = f"{elapsed // 3600:02}:{elapsed // 60 % 60:02}:{elapsed % 60:02}"
            with Image.open(image) as picture:
                if picture.format != "JPEG":
                    raise ValueError(f"Not a JPEG: {image}")
                picture.verify()
            digest = sha256(image)
            if digest in hashes:
                raise ValueError(f"Duplicate image: {image}")
            hashes.add(digest)
            identifier = f"CS2-{len(records) + 1:03}"
            records.append({
                "item_id": identifier,
                "filename": f"{identifier}.jpg",
                "map": map_name,
                "demo_file": demo_name,
                "demo_time": timestamp,
                "source_url": SOURCE_URL,
                "accessed_on": "2026-11-17",
                "accessed_at": "14:00",
                "source_type": "Демозапись матча Spirit — FURIA, BLAST Rivals 2026 Season 2",
                "license": "Не проверена; открытая лицензия не подтверждена",
                "original_relative_path": image.relative_to(source).as_posix(),
                "sha256": digest,
            })

    if len(records) < 50:
        raise ValueError(f"At least 50 screenshots required, found {len(records)}")
    images = PROJECT / "data/cs2_manual/images"
    manifest = PROJECT / "docs/cs2_sources.csv"
    archive = PROJECT / "data/cs2_frames.zip"
    if images.exists() or manifest.exists() or archive.exists():
        raise FileExistsError("Prepared output exists; refusing to overwrite it")
    images.mkdir(parents=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    for record in records:
        shutil.copyfile(source / record["original_relative_path"], images / record["filename"])
        assert sha256(images / record["filename"]) == record["sha256"]

    # UTF-8 BOM makes Cyrillic source notes readable in desktop Excel.
    with manifest.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    with ZipFile(archive, "x", compression=ZIP_DEFLATED) as bundle:
        for record in records:
            bundle.write(images / record["filename"], record["filename"])
    with ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert len(bundle.namelist()) == len(records)
        for record in records:
            assert hashlib.sha256(bundle.read(record["filename"])).hexdigest() == record["sha256"]
    with manifest.open(encoding="utf-8-sig", newline="") as stream:
        assert list(csv.DictReader(stream)) == records
    print(f"Prepared {len(records)} screenshots, unchanged originals and no exact duplicates.")
    print(f"Images: {images}")
    print(f"Sources: {manifest}")
    print(f"Archive: {archive} ({archive.stat().st_size / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    main()
