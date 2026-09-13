# Shared fake Supabase client for tests — stands in for supabase-py's
# query builder chain (select/in_/eq/update/insert/execute) so repo/router
# logic can be tested without a real database.

import json
from types import SimpleNamespace


class FakeQuery:
    def __init__(self, table: list[dict]):
        self._table = table
        self._rows = table
        self._payload: dict | None = None
        self._insert_payload: dict | None = None
        self._upsert_payloads: list[dict] | None = None
        self._on_conflict: str | None = None

    def select(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def in_(self, column: str, values) -> "FakeQuery":
        values = set(values)
        self._rows = [r for r in self._rows if r.get(column) in values]
        return self

    def eq(self, column: str, value) -> "FakeQuery":
        default = 0 if column == "revision" else None
        self._rows = [r for r in self._rows if r.get(column, default) == value]
        return self

    def filter(self, column: str, operator: str, criteria: str) -> "FakeQuery":
        if operator != "eq":
            raise NotImplementedError(f"FakeQuery does not support {operator}")
        try:
            value = json.loads(criteria)
        except json.JSONDecodeError:
            value = criteria
        return self.eq(column, value)

    def update(self, payload: dict) -> "FakeQuery":
        self._payload = payload
        return self

    def insert(self, payload: dict) -> "FakeQuery":
        self._insert_payload = dict(payload)
        return self

    def upsert(self, payload: dict | list[dict], on_conflict: str | None = None) -> "FakeQuery":
        # supabase-py accepts either a single row or a list of rows here;
        # normalize to a list so execute() only has one code path.
        self._upsert_payloads = [dict(p) for p in payload] if isinstance(payload, list) else [dict(payload)]
        self._on_conflict = on_conflict
        return self

    def execute(self) -> SimpleNamespace:
        if self._upsert_payloads is not None:
            # Mimics ON CONFLICT (on_conflict) DO UPDATE: match each row
            # against the unfiltered table by the conflict columns, update
            # in place if found, otherwise insert a new row.
            conflict_columns = [c.strip() for c in (self._on_conflict or "").split(",") if c.strip()]
            written = []
            for upsert_payload in self._upsert_payloads:
                existing = next(
                    (
                        row
                        for row in self._table
                        if conflict_columns and all(row.get(c) == upsert_payload.get(c) for c in conflict_columns)
                    ),
                    None,
                )
                if existing is not None:
                    existing.update(upsert_payload)
                    written.append(existing)
                else:
                    self._table.append(upsert_payload)
                    written.append(upsert_payload)
            return SimpleNamespace(data=written)
        if self._insert_payload is not None:
            # Mutate the underlying table (not just the filtered _rows view)
            # so a later fetch on the same fake client sees the new row.
            self._table.append(self._insert_payload)
            return SimpleNamespace(data=[self._insert_payload])
        if self._payload is not None:
            for row in self._rows:
                row.update(self._payload)
        return SimpleNamespace(data=self._rows)


class FakeSupabaseClient:
    def __init__(self, tables: dict[str, list[dict]]):
        self._tables = tables

    def table(self, name: str) -> FakeQuery:
        # setdefault so tests don't need to pre-declare every table they
        # don't care about (e.g. scoring tests that never touch `account`).
        return FakeQuery(self._tables.setdefault(name, []))
