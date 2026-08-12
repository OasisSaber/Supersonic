from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import (
    CHAR,
    CheckConstraint,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Inspector

from app.adapters.postgres.orm import Base

BUSINESS_TABLES = {"users", "platform_sessions", "audit_events"}
MIGRATED_TABLES = BUSINESS_TABLES | {"alembic_version"}
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def make_alembic_config() -> Config:
    return Config(str(BACKEND_ROOT / "alembic.ini"))


def _database_tables(inspector: Inspector) -> set[str]:
    return set(inspector.get_table_names(schema="public"))


def _normalize_column_type(column_type: Any) -> tuple[str, int | None, bool | None]:
    rendered = column_type.compile(dialect=postgresql.dialect())
    normalized_ddl = " ".join(str(rendered).upper().split())
    return (
        normalized_ddl,
        getattr(column_type, "length", None),
        getattr(column_type, "timezone", None),
    )


def _primary_key_signature(
    name: str | None,
    columns: list[str] | tuple[str, ...],
) -> tuple[str | None, tuple[str, ...]]:
    return name, tuple(columns)


def _normalize_check_expression(expression: str) -> str:
    normalized = expression.strip().lower()
    if normalized.startswith("check"):
        normalized = normalized.removeprefix("check").lstrip()
    normalized = re.sub(
        r"::\s*(?:character\s+varying|varchar|text)(?:\s*\[\s*\])?",
        "",
        normalized,
    )
    normalized = re.sub(r"=\s*any\b", " in ", normalized)
    normalized = re.sub(r"\barray\s*\[", "(", normalized)
    normalized = re.sub(
        (
            r"(?P<left>char_length\s*\(\s*\(*\s*[a-z_][a-z0-9_]*"
            r"\s*\)*\s*\))\s+between\s+(?P<lower>\d+)\s+and\s+"
            r"(?P<upper>\d+)"
        ),
        r"\g<left> >= \g<lower> and \g<left> <= \g<upper>",
        normalized,
    )

    result: list[str] = []
    in_literal = False
    position = 0
    while position < len(normalized):
        character = normalized[position]
        if character == "'":
            result.append(character)
            if in_literal and position + 1 < len(normalized) and normalized[position + 1] == "'":
                result.append("'")
                position += 2
                continue
            in_literal = not in_literal
        elif in_literal:
            result.append(character)
        elif character not in "()[]\"" and not character.isspace():
            result.append(character)
        position += 1
    return "".join(result)


def _metadata_foreign_keys(table_name: str) -> set[tuple[Any, ...]]:
    table = Base.metadata.tables[table_name]
    return {
        (
            constraint.name,
            tuple(constraint.columns.keys()),
            constraint.referred_table.name,
            tuple(element.column.name for element in constraint.elements),
            constraint.ondelete,
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }


def _database_foreign_keys(
    inspector: Inspector, table_name: str
) -> set[tuple[Any, ...]]:
    return {
        (
            foreign_key["name"],
            tuple(foreign_key["constrained_columns"]),
            foreign_key["referred_table"],
            tuple(foreign_key["referred_columns"]),
            foreign_key["options"].get("ondelete"),
        )
        for foreign_key in inspector.get_foreign_keys(table_name, schema="public")
    }


def _metadata_constraint_names(
    table_name: str, constraint_type: type[CheckConstraint] | type[UniqueConstraint]
) -> set[str | None]:
    return {
        constraint.name
        for constraint in Base.metadata.tables[table_name].constraints
        if isinstance(constraint, constraint_type)
    }


def _database_constraint_names(
    constraints: list[Mapping[str, Any]],
) -> set[str | None]:
    return {constraint["name"] for constraint in constraints}


def _metadata_checks(table_name: str) -> dict[str | None, str]:
    return {
        constraint.name: _normalize_check_expression(str(constraint.sqltext))
        for constraint in Base.metadata.tables[table_name].constraints
        if isinstance(constraint, CheckConstraint)
    }


def _database_checks(
    constraints: list[Mapping[str, Any]],
) -> dict[str | None, str]:
    return {
        constraint["name"]: _normalize_check_expression(constraint["sqltext"])
        for constraint in constraints
    }


def _metadata_indexes(table_name: str) -> set[tuple[Any, ...]]:
    dialect = postgresql.dialect()
    return {
        (
            index.name,
            index.unique,
            tuple(
                str(
                    expression.compile(
                        dialect=dialect,
                        compile_kwargs={"include_table": False},
                    )
                )
                for expression in index.expressions
            ),
        )
        for index in Base.metadata.tables[table_name].indexes
    }


def _database_indexes(
    inspector: Inspector, table_name: str
) -> set[tuple[Any, ...]]:
    indexes = set()
    for index in inspector.get_indexes(table_name, schema="public"):
        if index.get("duplicates_constraint"):
            continue

        expressions = index.get("expressions", ())
        column_sorting = index.get("column_sorting", {})
        ordered_expressions = []
        for position, column_name in enumerate(index["column_names"]):
            expression = column_name
            if expression is None:
                expression = expressions[position]
            sorting = column_sorting.get(expression, ())
            if sorting:
                expression = (
                    f"{expression} "
                    f"{' '.join(option.replace('_', ' ').upper() for option in sorting)}"
                )
            ordered_expressions.append(expression)

        indexes.add(
            (
                index["name"],
                index["unique"],
                tuple(ordered_expressions),
            )
        )
    return indexes


def test_empty_schema_upgrades_to_the_only_head(
    migrated_database_url: str,
) -> None:
    config = make_alembic_config()
    assert ScriptDirectory.from_config(config).get_heads() == ["20260809_0001"]

    engine = create_engine(migrated_database_url)
    try:
        with engine.connect() as connection:
            version = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            assert version == "20260809_0001"
            assert _database_tables(inspect(connection)) == MIGRATED_TABLES
    finally:
        engine.dispose()


def test_downgrade_removes_business_tables_and_upgrade_restores_them(
    migrated_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = make_alembic_config()
    with monkeypatch.context() as migration_environment:
        migration_environment.setenv("DATABASE_URL", migrated_database_url)
        command.downgrade(config, "base")

    engine = create_engine(migrated_database_url)
    try:
        with engine.connect() as connection:
            assert _database_tables(inspect(connection)).isdisjoint(BUSINESS_TABLES)
        with monkeypatch.context() as migration_environment:
            migration_environment.setenv("DATABASE_URL", migrated_database_url)
            command.upgrade(config, "head")
        with engine.connect() as connection:
            assert _database_tables(inspect(connection)) == MIGRATED_TABLES
    finally:
        engine.dispose()


def test_migration_schema_matches_orm_metadata(
    migrated_database_url: str,
) -> None:
    engine = create_engine(migrated_database_url)
    try:
        with engine.connect() as connection:
            inspector = inspect(connection)
            assert _database_tables(inspector) - {"alembic_version"} == set(
                Base.metadata.tables
            )

            for table_name, metadata_table in Base.metadata.tables.items():
                database_columns = {
                    column["name"]: column
                    for column in inspector.get_columns(table_name, schema="public")
                }
                assert set(database_columns) == set(metadata_table.columns.keys())
                assert {
                    name: column["nullable"]
                    for name, column in database_columns.items()
                } == {
                    column.name: column.nullable for column in metadata_table.columns
                }
                assert {
                    name: _normalize_column_type(column["type"])
                    for name, column in database_columns.items()
                } == {
                    column.name: _normalize_column_type(column.type)
                    for column in metadata_table.columns
                }
                database_primary_key = inspector.get_pk_constraint(
                    table_name,
                    schema="public",
                )
                assert _primary_key_signature(
                    database_primary_key["name"],
                    database_primary_key["constrained_columns"],
                ) == _primary_key_signature(
                    metadata_table.primary_key.name,
                    tuple(metadata_table.primary_key.columns.keys()),
                )
                assert _database_foreign_keys(
                    inspector, table_name
                ) == _metadata_foreign_keys(table_name)
                assert _database_constraint_names(
                    inspector.get_unique_constraints(table_name, schema="public")
                ) == _metadata_constraint_names(table_name, UniqueConstraint)
                assert _database_checks(
                    inspector.get_check_constraints(table_name, schema="public")
                ) == _metadata_checks(table_name)
                assert _database_indexes(inspector, table_name) == _metadata_indexes(
                    table_name
                )
    finally:
        engine.dispose()


def test_schema_parity_normalization_detects_column_type_and_length_mutations() -> None:
    assert _normalize_column_type(String(128)) != _normalize_column_type(String(64))
    assert _normalize_column_type(CHAR(64)) != _normalize_column_type(String(64))


def test_schema_parity_normalization_detects_primary_key_mutations() -> None:
    expected = _primary_key_signature("pk_users", ["id"])

    assert expected != _primary_key_signature("pk_users_v2", ["id"])
    assert expected != _primary_key_signature("pk_users", ["username_norm"])


def test_schema_parity_normalization_handles_postgresql_check_reflection() -> None:
    metadata_expression = "role IN ('admin', 'operator', 'viewer')"
    reflected_expression = (
        "((role)::text = ANY ((ARRAY['admin'::character varying, "
        "'operator'::character varying, 'viewer'::character varying])::text[]))"
    )
    mutated_expression = reflected_expression.replace("'viewer'", "'owner'")

    assert _normalize_check_expression(metadata_expression) == (
        _normalize_check_expression(reflected_expression)
    )
    assert _normalize_check_expression(metadata_expression) != (
        _normalize_check_expression(mutated_expression)
    )
