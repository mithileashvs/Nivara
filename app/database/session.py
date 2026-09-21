"""SQLAlchemy async database interface and table repository for Nivara.

Translates high-level query operations to parameterized SQLAlchemy Core SQL queries
supporting PostgreSQL (Supabase / asyncpg) and SQLite (aiosqlite).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Index,
    String,
    Table,
    and_,
    asc,
    desc,
    false,
    func,
    or_,
    select,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from app.database.collections import C
from app.database.tables import TABLE_MAP, metadata

logger = logging.getLogger("nivara.db")


class DuplicateKeyError(Exception):
    """Raised when a unique constraint or duplicate key violation occurs."""



def _serialize_for_db(val: Any) -> Any:
    if isinstance(val, (dict, list)):
        return val
    return val


def _normalize_row(row_dict: dict[str, Any], table_name: str) -> dict[str, Any]:
    """Ensure both `_id` and `id` exist, and nested JSON fields are parsed."""
    out = dict(row_dict)
    if "id" in out:
        out["id"] = str(out["id"])
        out["_id"] = out["id"]
    for k, v in out.items():
        if k in ("department_ids", "hospital_ids", "consultation_types", "documents",
                 "keywords", "notified_slot_ids", "managed_hospital_ids", "location",
                 "contact", "basic_information", "data") and isinstance(v, str):
            try:
                out[k] = json.loads(v)
            except Exception:
                pass
    return out


def _is_valid_uuid(val: Any) -> bool:
    if isinstance(val, uuid.UUID):
        return True
    try:
        val_str = str(val)
        if len(val_str) not in (32, 36):
            return False
        uuid.UUID(val_str)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


class TableRepository:
    def __init__(self, db: Database, table: Table, name: str) -> None:
        self.db = db
        self.table = table
        self.name = name

    def _build_criterion(self, key: str, value: Any) -> Any:
        col_name = "id" if key == "_id" else key
        if "." in col_name:
            # Embedded JSON property query, e.g. location.city_normalized
            parts = col_name.split(".", 1)
            json_col = getattr(self.table.c, parts[0], None)
            if json_col is not None:
                field = parts[1]
                is_pg = self.db.engine.dialect.name == "postgresql"
                expr = json_col.op("->>")(field) if is_pg else func.json_extract(json_col, f"$.{field}")
                if isinstance(value, dict):
                    clauses = []
                    for op, op_val in value.items():
                        if op == "$ne":
                            if op_val is None:
                                clauses.append(expr.isnot(None))
                            else:
                                clauses.append(expr != str(getattr(op_val, "value", op_val)))
                        elif op == "$in":
                            vals = [str(getattr(v, "value", v)) for v in op_val]
                            clauses.append(expr.in_(vals))
                    return and_(*clauses) if clauses else true()
                elif value is None:
                    return expr.is_(None)
                else:
                    v_clean = str(getattr(value, "value", value))
                    return expr == v_clean
            return true()

        col = getattr(self.table.c, col_name, None)
        if col is None:
            return true()

        is_json_col = col.type.__class__.__name__ in ("JSON", "JSONB")
        if is_json_col:
            if isinstance(value, dict):
                clauses = []
                for op, op_val in value.items():
                    val_str = str(getattr(op_val, "value", op_val))
                    if op == "$ne":
                        clauses.append(~col.cast(String).contains(f'"{val_str}"'))
                    elif op == "$in":
                        or_items = [col.cast(String).contains(f'"{str(getattr(v, "value", v))}"') for v in op_val]
                        clauses.append(or_(*or_items) if or_items else false())
                    elif op == "$nin":
                        and_items = [~col.cast(String).contains(f'"{str(getattr(v, "value", v))}"') for v in op_val]
                        clauses.append(and_(*and_items) if and_items else true())
                return and_(*clauses) if clauses else true()
            elif value is None:
                return col.is_(None)
            else:
                val_str = str(getattr(value, "value", value))
                return col.cast(String).contains(f'"{val_str}"')

        is_uuid_col = col.type.__class__.__name__ in ("Uuid", "UUID")

        if isinstance(value, dict):
            clauses = []
            for op, op_val in value.items():
                if op == "$in":
                    if is_uuid_col:
                        vals = [str(getattr(v, "value", v)) for v in op_val if _is_valid_uuid(getattr(v, "value", v))]
                        if not vals:
                            return false()
                        clauses.append(col.in_(vals))
                    else:
                        vals = [str(getattr(v, "value", v)) for v in op_val]
                        clauses.append(col.in_(vals))
                elif op == "$nin":
                    if is_uuid_col:
                        vals = [str(getattr(v, "value", v)) for v in op_val if _is_valid_uuid(getattr(v, "value", v))]
                        if vals:
                            clauses.append(~col.in_(vals))
                    else:
                        vals = [str(getattr(v, "value", v)) for v in op_val]
                        clauses.append(~col.in_(vals))
                elif op == "$ne":
                    op_v = getattr(op_val, "value", op_val)
                    if op_v is None:
                        clauses.append(col.isnot(None))
                    elif is_uuid_col and not _is_valid_uuid(op_v):
                        pass  # value cannot equal an invalid uuid
                    else:
                        clauses.append(col != str(op_v))
                elif op == "$gte":
                    clauses.append(col >= getattr(op_val, "value", op_val))
                elif op == "$lte":
                    clauses.append(col <= getattr(op_val, "value", op_val))
                elif op == "$gt":
                    clauses.append(col > getattr(op_val, "value", op_val))
                elif op == "$lt":
                    clauses.append(col < getattr(op_val, "value", op_val))
                elif op == "$regex":
                    import re as _re
                    pattern = str(op_val).lstrip("^").rstrip("$")
                    clean_pattern = _re.sub(r"\\(.)", r"\1", pattern)
                    clauses.append(col.ilike(f"%{clean_pattern}%"))
            return and_(*clauses) if clauses else true()
        elif value is None:
            return col.is_(None)
        else:
            v_clean = getattr(value, "value", value)
            if is_uuid_col:
                if not _is_valid_uuid(v_clean):
                    return false()
                return col == str(v_clean)
            if col_name == "id" or col_name.endswith("_id") or col_name in ("patient_user_id", "doctor_user_id", "changed_by"):
                return col == str(v_clean)
            return col == v_clean

    def _build_where(self, filter_dict: dict[str, Any]) -> Any:
        if not filter_dict:
            return True
        clauses = []
        for key, value in filter_dict.items():
            if key == "$or":
                or_clauses = [self._build_where(cond) for cond in value]
                clauses.append(or_(*or_clauses))
            elif key == "$and":
                and_clauses = [self._build_where(cond) for cond in value]
                clauses.append(and_(*and_clauses))
            else:
                clauses.append(self._build_criterion(key, value))
        return and_(*clauses) if clauses else True

    async def find_one(self, filter_dict: dict[str, Any], projection: dict[str, Any] | None = None) -> dict[str, Any] | None:
        stmt = select(self.table).where(self._build_where(filter_dict)).limit(1)
        async with self.db.connect() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().first()
            if row is None:
                return None
            return _normalize_row(dict(row), self.name)

    async def count_documents(self, filter_dict: dict[str, Any]) -> int:
        stmt = select(func.count()).select_from(self.table).where(self._build_where(filter_dict))
        async with self.db.connect() as conn:
            result = await conn.execute(stmt)
            return result.scalar_one() or 0

    def find(self, filter_dict: dict[str, Any] | None = None, projection: dict[str, Any] | None = None):
        return QueryCursor(self, filter_dict or {})

    async def insert_one(self, doc: dict[str, Any]) -> InsertOneResult:
        data = dict(doc)
        if "_id" in data:
            data["id"] = str(data.pop("_id"))
        elif "id" not in data or not data["id"]:
            data["id"] = str(uuid4())
        else:
            data["id"] = str(data["id"])

        now = datetime.now(timezone.utc)
        if "created_at" in self.table.c and ("created_at" not in data or data["created_at"] is None):
            data["created_at"] = now
        if "updated_at" in self.table.c and ("updated_at" not in data or data["updated_at"] is None):
            data["updated_at"] = now

        filtered_data = {}
        for k, v in data.items():
            if k in self.table.c:
                filtered_data[k] = _serialize_for_db(v)

        stmt = self.table.insert().values(**filtered_data)
        async with self.db.connect() as conn:
            try:
                await conn.execute(stmt)
                await conn.commit()
            except IntegrityError as exc:
                await conn.rollback()
                raise DuplicateKeyError(str(exc)) from exc
        return InsertOneResult(data["id"])

    async def insert_many(self, docs: list[dict[str, Any]]) -> list[str]:
        ids = []
        for doc in docs:
            res = await self.insert_one(doc)
            ids.append(res.inserted_id)
        return ids

    async def update_one(self, filter_dict: dict[str, Any], update_dict: dict[str, Any], upsert: bool = False) -> UpdateResult:
        set_vals = update_dict.get("$set", {})
        add_to_set = update_dict.get("$addToSet", {})
        inc_vals = update_dict.get("$inc", {})

        target = await self.find_one(filter_dict)
        if target is None:
            if upsert:
                new_doc = dict(filter_dict)
                new_doc.update(update_dict.get("$setOnInsert", {}))
                new_doc.update(set_vals)
                res = await self.insert_one(new_doc)
                return UpdateResult(matched=0, modified=1, upserted_id=res.inserted_id)
            return UpdateResult(matched=0, modified=0)

        def _clean_val(v: Any) -> Any:
            v = getattr(v, "value", v)
            if hasattr(v, "__class__") and v.__class__.__name__ == "ObjectId":
                return str(v)
            return v

        values_to_update: dict[str, Any] = {}
        for k, v in set_vals.items():
            col_name = "id" if k == "_id" else k
            if hasattr(self.table.c, col_name):
                values_to_update[col_name] = _clean_val(v)

        for k, v in add_to_set.items():
            col_name = "id" if k == "_id" else k
            current_list = list(target.get(col_name) or [])
            item = _clean_val(v)
            if item not in current_list:
                current_list.append(item)
            values_to_update[col_name] = current_list

        for k, v in inc_vals.items():
            col_name = "id" if k == "_id" else k
            if hasattr(self.table.c, col_name):
                values_to_update[col_name] = getattr(self.table.c, col_name) + v

        if not values_to_update:
            return UpdateResult(matched=1, modified=0)

        stmt = (
            self.table.update()
            .where(self.table.c.id == target["id"])
            .values(**values_to_update)
        )
        async with self.db.connect() as conn:
            await conn.execute(stmt)
            await conn.commit()
        return UpdateResult(matched=1, modified=1)

    async def update_many(self, filter_dict: dict[str, Any], update_dict: dict[str, Any]) -> UpdateResult:
        def _clean_val(v: Any) -> Any:
            v = getattr(v, "value", v)
            if hasattr(v, "__class__") and v.__class__.__name__ == "ObjectId":
                return str(v)
            return v

        set_vals = update_dict.get("$set", {})
        values_to_update = {("id" if k == "_id" else k): _clean_val(v)
                            for k, v in set_vals.items() if hasattr(self.table.c, "id" if k == "_id" else k)}
        stmt = (
            self.table.update()
            .where(self._build_where(filter_dict))
            .values(**values_to_update)
        )
        async with self.db.connect() as conn:
            res = await conn.execute(stmt)
            await conn.commit()
            count = res.rowcount if res.rowcount is not None and res.rowcount >= 0 else 0
            return UpdateResult(matched=count, modified=count)

    async def find_one_and_update(
        self,
        filter_dict: dict[str, Any],
        update_dict: dict[str, Any],
        return_document: Any = True,
    ) -> dict[str, Any] | None:
        """Atomic conditional update using SQL UPDATE ... RETURNING *.
        
        Guarantees that state transitions only occur when the row matches the exact filter conditions.
        Returns the updated row, or None if the condition was not met (conflict / concurrency loser).
        """
        def _clean_val(v: Any) -> Any:
            v = getattr(v, "value", v)
            if hasattr(v, "__class__") and v.__class__.__name__ == "ObjectId":
                return str(v)
            return v

        set_vals = update_dict.get("$set", {})
        values_to_update = {("id" if k == "_id" else k): _clean_val(v)
                            for k, v in set_vals.items() if hasattr(self.table.c, "id" if k == "_id" else k)}

        stmt = (
            self.table.update()
            .where(self._build_where(filter_dict))
            .values(**values_to_update)
            .returning(self.table)
        )
        async with self.db.connect() as conn:
            try:
                res = await conn.execute(stmt)
                row = res.mappings().first()
                await conn.commit()
            except IntegrityError as exc:
                await conn.rollback()
                raise DuplicateKeyError(str(exc)) from exc
            if row is None:
                return None
            return _normalize_row(dict(row), self.name)

    async def delete_one(self, filter_dict: dict[str, Any]) -> DeleteResult:
        subq = select(self.table.c.id).where(self._build_where(filter_dict)).limit(1).scalar_subquery()
        stmt = self.table.delete().where(self.table.c.id == subq)
        async with self.db.connect() as conn:
            res = await conn.execute(stmt)
            await conn.commit()
            count = res.rowcount if res.rowcount is not None and res.rowcount >= 0 else 0
            return DeleteResult(deleted_count=count)

    async def delete_many(self, filter_dict: dict[str, Any]) -> DeleteResult:
        stmt = self.table.delete().where(self._build_where(filter_dict))
        async with self.db.connect() as conn:
            res = await conn.execute(stmt)
            await conn.commit()
            count = res.rowcount if res.rowcount is not None and res.rowcount >= 0 else 0
            return DeleteResult(deleted_count=count)

    async def create_index(self, keys: list[tuple[str, int]], unique: bool = False, name: str | None = None, **kw) -> None:
        """No-op on existing tables (indexes are managed via metadata / migrations)."""
        pass

    def aggregate(self, pipeline: list[dict[str, Any]]) -> AggregateCursor:
        return AggregateCursor(self.db, self.name, pipeline)


class QueryCursor:
    def __init__(self, repo: TableRepository, filter_dict: dict[str, Any]) -> None:
        self.repo = repo
        self.filter_dict = filter_dict
        self._sort_clauses: list[Any] = []
        self._skip_val: int = 0
        self._limit_val: int | None = None

    def sort(self, key_or_list: str | list[tuple[str, int]], direction: int | None = None) -> QueryCursor:
        pairs = key_or_list if isinstance(key_or_list, list) else [(key_or_list, direction or 1)]
        for k, d in pairs:
            col_name = "id" if k == "_id" else k
            col = getattr(self.repo.table.c, col_name, None)
            if col is not None:
                self._sort_clauses.append(asc(col) if d == 1 else desc(col))
        return self

    def skip(self, n: int) -> QueryCursor:
        self._skip_val = n
        return self

    def limit(self, n: int) -> QueryCursor:
        self._limit_val = n
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        stmt = select(self.repo.table).where(self.repo._build_where(self.filter_dict))
        if self._sort_clauses:
            stmt = stmt.order_by(*self._sort_clauses)
        if self._skip_val:
            stmt = stmt.offset(self._skip_val)
        limit = length if length is not None else self._limit_val
        if limit is not None:
            stmt = stmt.limit(limit)

        async with self.repo.db.connect() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().all()
            return [_normalize_row(dict(r), self.repo.name) for r in rows]

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        items = await self.to_list()
        for item in items:
            yield item


class AggregateCursor:
    def __init__(self, db: Database, table_name: str, pipeline: list[dict[str, Any]]) -> None:
        self.db = db
        self.table_name = table_name
        self.pipeline = pipeline
        self._items: list[dict[str, Any]] | None = None

    async def _load(self) -> list[dict[str, Any]]:
        if self._items is None:
            self._items = await self.db._run_aggregation(self.table_name, self.pipeline)
        return self._items

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        items = await self._load()
        return items[:length] if length is not None else items

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        items = await self._load()
        for item in items:
            yield item


class InsertOneResult:
    def __init__(self, inserted_id: str) -> None:
        self.inserted_id = inserted_id


class UpdateResult:
    def __init__(self, matched: int, modified: int, upserted_id: str | None = None) -> None:
        self.matched_count = matched
        self.modified_count = modified
        self.upserted_id = upserted_id


class DeleteResult:
    def __init__(self, deleted_count: int) -> None:
        self.deleted_count = deleted_count


class Database:
    """Async database abstraction providing access to tables by name or attribute."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self._repos: dict[str, TableRepository] = {}
        for name, table in TABLE_MAP.items():
            self._repos[name] = TableRepository(self, table, name)

    def __getitem__(self, name: str) -> TableRepository:
        if name in self._repos:
            return self._repos[name]
        raise KeyError(f"Table '{name}' not found")

    def __getattr__(self, name: str) -> TableRepository:
        if name in self._repos:
            return self._repos[name]
        raise AttributeError(f"Table '{name}' not found")

    def connect(self) -> AsyncConnection:
        return self.engine.connect()

    async def ensure_indexes(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(metadata.create_all)
            # Create partial unique indexes if PostgreSQL
            if self.engine.dialect.name == "postgresql":
                await conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_appointments_active_slot "
                    "ON appointments (slot_id) WHERE is_active = TRUE;"
                ))
                await conn.execute(text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_appointments_active_patient_start "
                    "ON appointments (patient_id, start_at) WHERE is_active = TRUE;"
                ))

    async def command(self, cmd: str) -> Any:
        if cmd == "ping":
            async with self.connect() as conn:
                await conn.execute(text("SELECT 1;"))
            return {"ok": 1.0}
        raise NotImplementedError(f"Unknown command: {cmd}")

    async def ping(self) -> bool:
        async with self.connect() as conn:
            await conn.execute(text("SELECT 1;"))
        return True

    async def _run_aggregation(self, table_name: str, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Handle specific aggregation pipelines used by business services."""
        # Check for status count group pipeline in admin_service
        if table_name == C.APPOINTMENTS and any("$group" in s and s["$group"].get("_id") == "$status" for s in pipeline):
            stmt = select(TABLE_MAP[table_name].c.status, func.count().label("n")).group_by(TABLE_MAP[table_name].c.status)
            async with self.connect() as conn:
                res = await conn.execute(stmt)
                return [{"_id": str(r.status.value if hasattr(r.status, "value") else r.status), "n": r.n} for r in res]

        # Check for slots by department pipeline in hospital_service
        if table_name == C.APPOINTMENT_SLOTS and any("$group" in s and s["$group"].get("_id") == "$department_id" for s in pipeline):
            match_dict = {}
            for stage in pipeline:
                if "$match" in stage:
                    match_dict.update(stage["$match"])
            repo = self._repos[table_name]
            stmt = (
                select(repo.table.c.department_id, func.count().label("n"))
                .where(repo._build_where(match_dict))
                .group_by(repo.table.c.department_id)
            )
            async with self.connect() as conn:
                res = await conn.execute(stmt)
                return [{"_id": r.department_id, "n": r.n} for r in res]

        # Doctor distinct patient count in doctor_service
        if table_name == C.APPOINTMENTS and any("$group" in s and s["$group"].get("_id") == "$patient_id" for s in pipeline):
            match_dict = {}
            for stage in pipeline:
                if "$match" in stage:
                    match_dict.update(stage["$match"])
            repo = self._repos[table_name]
            stmt = select(repo.table.c.patient_id).where(repo._build_where(match_dict)).distinct()
            async with self.connect() as conn:
                res = await conn.execute(stmt)
                return [{"_id": r[0]} for r in res]

        # Doctor matching / slots search group pipeline in doctor_matching_service or doctor_service
        if table_name == C.APPOINTMENT_SLOTS and any("$group" in s and s["$group"].get("_id") == "$doctor_id" for s in pipeline):
            is_push = any("$group" in s and "slots" in s["$group"] for s in pipeline)
            match_dict = {}
            for stage in pipeline:
                if "$match" in stage:
                    match_dict.update(stage["$match"])
            repo = self._repos[table_name]
            if is_push:
                stmt = (
                    select(repo.table)
                    .where(repo._build_where(match_dict))
                    .order_by(asc(repo.table.c.start_at))
                )
                async with self.connect() as conn:
                    res = await conn.execute(stmt)
                    rows = [_normalize_row(dict(r), table_name) for r in res.mappings().all()]
                    grouped: dict[str, list[dict[str, Any]]] = {}
                    for r in rows:
                        grouped.setdefault(r["doctor_id"], []).append(r)
                    return [{"_id": doc_id, "slots": slots} for doc_id, slots in grouped.items()]
            else:
                stmt = (
                    select(repo.table.c.doctor_id)
                    .where(repo._build_where(match_dict))
                    .distinct()
                )
                async with self.connect() as conn:
                    res = await conn.execute(stmt)
                    return [{"_id": r[0]} for r in res]

        # Fallback empty list
        return []
