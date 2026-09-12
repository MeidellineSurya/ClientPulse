# Shared fake Supabase client for tests — stands in for supabase-py's
# query builder chain (select/in_/eq/update/insert/execute) so repo/router
# logic can be tested without a real database.

from types import SimpleNamespace


class FakeQuery:
    def __init__(self, table: list[dict]):
        self._table = table
        self._rows = table
        self._payload: dict | None = None
        self._insert_payload: dict | None = None

    def select(self, *_args, **_kwargs) -> "FakeQuery":
        return self

    def in_(self, column: str, values) -> "FakeQuery":
        values = set(values)
        self._rows = [r for r in self._rows if r.get(column) in values]
        return self

    def eq(self, column: str, value) -> "FakeQuery":
        self._rows = [r for r in self._rows if r.get(column) == value]
        return self

    def update(self, payload: dict) -> "FakeQuery":
        self._payload = payload
        return self

    def insert(self, payload: dict) -> "FakeQuery":
        self._insert_payload = dict(payload)
        return self

    def execute(self) -> SimpleNamespace:
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
        return FakeQuery(self._tables[name])
