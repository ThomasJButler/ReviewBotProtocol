"""A database created by an older version gains the columns the models now
declare, in place, so nobody has to delete reviews.db for a new column."""

from sqlalchemy import create_engine, inspect, text

from database.connection import Base, add_missing_columns
from database import models  # noqa: F401  registers the tables


def test_missing_columns_are_added_to_an_existing_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/old.db")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE reviews (id VARCHAR(36) PRIMARY KEY, repository VARCHAR(255) NOT NULL, "
                          "pr_number INTEGER NOT NULL, status VARCHAR(20) NOT NULL)"))
        added = add_missing_columns(conn)
    assert "reviews.progress_phase" in added and "reviews.progress_done" in added
    with engine.connect() as conn:
        names = {c["name"] for c in inspect(conn).get_columns("reviews")}
        assert {"progress_phase", "progress_done", "progress_total", "progress_file", "files_total"} <= names
        conn.execute(text("INSERT INTO reviews (id, repository, pr_number, status) VALUES ('r1', 'o/r', 1, 'running')"))
        row = conn.execute(text("SELECT progress_done, files_total FROM reviews WHERE id = 'r1'")).one()
        assert tuple(row) == (0, 0), "integer columns arrive with their default"
    with engine.begin() as conn:
        assert add_missing_columns(conn) == [], "a second pass has nothing to add"


def test_a_fresh_database_needs_nothing_added(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/new.db")
    with engine.begin() as conn:
        Base.metadata.create_all(conn)
        assert add_missing_columns(conn) == []
