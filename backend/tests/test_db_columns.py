"""A database created by an older version gains the columns and indexes the
models now declare, in place, so nobody has to delete reviews.db for them."""

from sqlalchemy import create_engine, inspect, text

from database.connection import Base, add_missing_columns, add_missing_indexes
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


OLD_DELIVERIES = ("CREATE TABLE webhook_deliveries (delivery_id VARCHAR(100) PRIMARY KEY, event VARCHAR(50) NOT NULL, "
                  "body_sha256 VARCHAR(64), received_at DATETIME NOT NULL, status VARCHAR(20) NOT NULL)")


def _index_names(conn, table):
    return {ix["name"]: ix for ix in inspect(conn).get_indexes(table)}


def test_the_unique_index_on_the_delivery_hash_is_added_to_an_existing_table(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/old.db")
    with engine.begin() as conn:
        conn.execute(text(OLD_DELIVERIES))
        conn.execute(text("INSERT INTO webhook_deliveries VALUES ('d1', 'ping', 'h1', '2026-01-01', 'pong'), "
                          "('d2', 'ping', NULL, '2026-01-01', 'pong'), ('d3', 'ping', NULL, '2026-01-01', 'pong')"))
        first = add_missing_indexes(conn)
        assert "ix_webhook_deliveries_body_sha256_unique" in first, "two NULL hashes are not duplicates"
        assert "ix_webhook_deliveries_repository" not in first, "a column the old table lacks has no index until the column exists"
        add_missing_columns(conn)
        assert add_missing_indexes(conn) == ["ix_webhook_deliveries_repository"], "the column's index follows the column"
    with engine.connect() as conn:
        assert _index_names(conn, "webhook_deliveries")["ix_webhook_deliveries_body_sha256_unique"]["unique"]
    with engine.begin() as conn:
        assert add_missing_indexes(conn) == [], "a second pass has nothing to add"


def test_a_table_with_duplicate_hashes_keeps_booting_without_the_index(tmp_path, caplog):
    import logging
    engine = create_engine(f"sqlite:///{tmp_path}/dupes.db")
    with engine.begin() as conn:
        conn.execute(text(OLD_DELIVERIES))
        conn.execute(text("INSERT INTO webhook_deliveries VALUES ('d1', 'ping', 'same', '2026-01-01', 'pong'), "
                          "('d2', 'ping', 'same', '2026-01-01', 'pong')"))
        add_missing_columns(conn)
        with caplog.at_level(logging.WARNING):
            created = add_missing_indexes(conn)
        assert "ix_webhook_deliveries_body_sha256_unique" not in created and "ix_webhook_deliveries_repository" in created
    with engine.connect() as conn:
        assert "ix_webhook_deliveries_body_sha256_unique" not in _index_names(conn, "webhook_deliveries")


def test_a_fresh_database_has_the_unique_index_from_create_all(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/new.db")
    with engine.begin() as conn:
        Base.metadata.create_all(conn)
        assert add_missing_indexes(conn) == []
        assert _index_names(conn, "webhook_deliveries")["ix_webhook_deliveries_body_sha256_unique"]["unique"]
        conn.execute(text("INSERT INTO webhook_deliveries (delivery_id, event, body_sha256, received_at, status) "
                          "VALUES ('d1', 'ping', 'h1', '2026-01-01', 'pong')"))
        import pytest
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            conn.execute(text("INSERT INTO webhook_deliveries (delivery_id, event, body_sha256, received_at, status) "
                              "VALUES ('d2', 'ping', 'h1', '2026-01-01', 'pong')"))
