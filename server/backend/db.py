import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "state.db"
# 사전 적재 루트. 각 yml stem 폴더가 카테고리(template)이며 그 안에 PDF/이미지가 평면으로 놓인다.
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def init() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as cx:
        cx.executescript(
            """
            CREATE TABLE IF NOT EXISTS applications (
                application_id TEXT PRIMARY KEY,
                filename       TEXT NOT NULL,
                status         TEXT NOT NULL DEFAULT 'blank',
                page_count     INTEGER NOT NULL,
                template_name  TEXT,
                source_path    TEXT
            );

            CREATE TABLE IF NOT EXISTS jobs (
                job_id     TEXT PRIMARY KEY,
                model      TEXT NOT NULL,
                device     TEXT NOT NULL,
                status     TEXT NOT NULL,
                field_spec TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS job_applications (
                job_id         TEXT NOT NULL,
                application_id TEXT NOT NULL,
                ord            INTEGER NOT NULL,
                PRIMARY KEY (job_id, application_id),
                FOREIGN KEY (job_id) REFERENCES jobs(job_id),
                FOREIGN KEY (application_id) REFERENCES applications(application_id)
            );

            CREATE TABLE IF NOT EXISTS field_results (
                job_id         TEXT NOT NULL,
                application_id TEXT NOT NULL,
                key            TEXT NOT NULL,
                predicted      TEXT,
                accuracy       REAL,
                edited         TEXT,
                PRIMARY KEY (job_id, application_id, key)
            );
            """
        )
        # 구버전 스키마(template_name/source_path 누락) → 멱등 ALTER. SQLite 는 IF NOT EXISTS
        # 가 ADD COLUMN 에 없어 PRAGMA 로 직접 검사.
        cols = {r["name"] for r in cx.execute("PRAGMA table_info(applications)").fetchall()}
        if "template_name" not in cols:
            cx.execute("ALTER TABLE applications ADD COLUMN template_name TEXT")
        if "source_path" not in cols:
            cx.execute("ALTER TABLE applications ADD COLUMN source_path TEXT")


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
