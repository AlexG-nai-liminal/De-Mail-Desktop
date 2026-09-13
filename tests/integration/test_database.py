import sqlite3
from pathlib import Path

import pytest

from demail.persistence import database as database_module
from demail.persistence.database import LATEST_SCHEMA_VERSION, Database, MigrationError


def operation(selected_count: int) -> dict[str, object]:
    return {
        "created_at": "2026-09-09T14:30:00Z",
        "account_email": "someone@example.com",
        "selection_json": "{}",
        "selection_description": "All mail",
        "destination_path": r"C:\Archives",
        "archive_folder_name": "2026-09-09_1430 all-mail",
        "selected_count": selected_count,
    }


def test_fresh_database_migrates_to_latest_schema(tmp_path: Path) -> None:
    database = Database(tmp_path / "de-mail.db")
    database.migrate()
    with database.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == LATEST_SCHEMA_VERSION
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {"archive_operations", "archive_messages", "archive_destinations"} <= tables


def test_migration_is_idempotent(tmp_path: Path) -> None:
    database = Database(tmp_path / "de-mail.db")
    database.migrate()
    database.migrate()
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM archive_operations").fetchone()[0] == 0


def test_existing_schema_one_database_gains_inline_attachment_total(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(database_module.MIGRATIONS[1])
        connection.execute("PRAGMA user_version = 1")
        connection.execute(
            "INSERT INTO archive_operations "
            "(created_at, account_email, selection_json, selection_description, "
            "destination_path, archive_folder_name, selected_count) "
            "VALUES ('2026-09-09T00:00:00Z', 'old@example.com', '{}', 'All mail', "
            "'C:/Archive', 'old', 0)"
        )
    Database(path).migrate()
    with sqlite3.connect(path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        inline_total = connection.execute(
            "SELECT inline_attachment_count FROM archive_operations"
        ).fetchone()[0]
    assert version == LATEST_SCHEMA_VERSION
    assert inline_total == 0


def test_operation_and_all_selected_rows_are_inserted_atomically(tmp_path: Path) -> None:
    database = Database(tmp_path / "de-mail.db")
    database.migrate()
    operation_id = database.create_operation_with_messages(operation(3), ["c", "a", "b"])
    with database.connect() as connection:
        selected = connection.execute(
            "SELECT selected_count FROM archive_operations WHERE id = ?", (operation_id,)
        ).fetchone()[0]
        ids = [
            row[0]
            for row in connection.execute(
                "SELECT gmail_message_id FROM archive_messages WHERE operation_id = ? "
                "ORDER BY gmail_message_id",
                (operation_id,),
            )
        ]
    assert selected == 3
    assert ids == ["a", "b", "c"]


@pytest.mark.parametrize("ids,count", [(["a"], 2), (["a", "a"], 2)])
def test_invalid_materialized_selection_does_not_create_operation(
    tmp_path: Path, ids: list[str], count: int
) -> None:
    database = Database(tmp_path / "de-mail.db")
    database.migrate()
    with pytest.raises(ValueError):
        database.create_operation_with_messages(operation(count), ids)
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM archive_operations").fetchone()[0] == 0


def test_database_constraints_reject_invalid_counters(tmp_path: Path) -> None:
    database = Database(tmp_path / "de-mail.db")
    database.migrate()
    invalid = operation(0)
    invalid["selected_count"] = -1
    with database.connect() as connection, pytest.raises(sqlite3.IntegrityError):
        columns = tuple(invalid)
        connection.execute(
            f"INSERT INTO archive_operations ({', '.join(columns)}) VALUES "
            f"({', '.join('?' for _ in columns)})",
            tuple(invalid.values()),
        )


def test_foreign_keys_prevent_orphan_message(tmp_path: Path) -> None:
    database = Database(tmp_path / "de-mail.db")
    database.migrate()
    with database.connect() as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO archive_messages (operation_id, gmail_message_id) VALUES (999, 'x')"
        )


def test_newer_database_is_refused_without_modification(tmp_path: Path) -> None:
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 99")
    with pytest.raises(MigrationError, match="newer"):
        Database(path).migrate()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99


def test_failed_migration_rolls_back_partial_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "broken.db"
    monkeypatch.setitem(
        database_module.MIGRATIONS,
        1,
        "CREATE TABLE should_roll_back (id INTEGER); THIS IS NOT SQL;",
    )
    with pytest.raises(MigrationError, match="schema 1 failed"):
        Database(path).migrate()
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE name = 'should_roll_back'"
        ).fetchone()
    assert table is None
