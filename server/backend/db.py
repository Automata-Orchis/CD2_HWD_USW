import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "state.db"
UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"


def init() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as cx:
        cx.executescript(
            """
            CREATE TABLE IF NOT EXISTS images (
                image_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                path     TEXT NOT NULL,
                status   TEXT NOT NULL DEFAULT 'blank'
            );

            CREATE TABLE IF NOT EXISTS jobs (
                job_id     TEXT PRIMARY KEY,
                model      TEXT NOT NULL,
                device     TEXT NOT NULL,
                status     TEXT NOT NULL,
                field_spec TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS job_images (
                job_id   TEXT NOT NULL,
                image_id TEXT NOT NULL,
                ord      INTEGER NOT NULL,
                PRIMARY KEY (job_id, image_id),
                FOREIGN KEY (job_id) REFERENCES jobs(job_id),
                FOREIGN KEY (image_id) REFERENCES images(image_id)
            );

            CREATE TABLE IF NOT EXISTS field_results (
                job_id    TEXT NOT NULL,
                image_id  TEXT NOT NULL,
                key       TEXT NOT NULL,
                predicted TEXT,
                accuracy  REAL,
                edited    TEXT,
                PRIMARY KEY (job_id, image_id, key)
            );
            """
        )


@contextmanager
def connect():
    cx = sqlite3.connect(DB_PATH)
    cx.row_factory = sqlite3.Row
    try:
        yield cx
        cx.commit()
    finally:
        cx.close()


def dump_field_spec(spec_list) -> str:
    return json.dumps([s.model_dump() if hasattr(s, "model_dump") else s for s in spec_list])


def load_field_spec(text: str) -> list[dict]:
    return json.loads(text)
