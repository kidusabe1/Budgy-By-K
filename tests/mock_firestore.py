"""Lightweight in-memory Firestore mock for unit tests.

Supports the subset of the Firestore API used by
``FirestoreExpenseManager`` and ``firestore_merchant_map``:

- Client.collection() / .batch()
- CollectionRef.document() / .add() / .where() / .order_by() / .limit() / .stream()
- DocumentRef.set() / .get() / .delete() / .collection()  (subcollections)
- Query chaining (.where().order_by().limit().stream())
- Batch .set() / .delete() / .commit()
- DocumentSnapshot .id / .to_dict() / .exists / .reference
"""

from __future__ import annotations

import copy
import operator
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------

class MockDocumentSnapshot:
    def __init__(self, doc_id: str, data: Optional[Dict], ref: "MockDocumentRef"):
        self._id = doc_id
        self._data = data
        self._ref = ref

    @property
    def id(self) -> str:
        return self._id

    @property
    def exists(self) -> bool:
        return self._data is not None

    @property
    def reference(self) -> "MockDocumentRef":
        return self._ref

    def to_dict(self) -> Optional[Dict]:
        if self._data is None:
            return None
        return copy.deepcopy(self._data)


# ---------------------------------------------------------------------------
# Document reference
# ---------------------------------------------------------------------------

class MockDocumentRef:
    def __init__(self, store: Dict, path: List[str]):
        # *store* is the root dict shared by the whole MockFirestoreClient.
        # *path* is e.g. ["users", "abc", "transactions", "doc1"]
        self._store = store
        self._path = path

    @property
    def id(self) -> str:
        return self._path[-1]

    # -- navigation --------------------------------------------------------

    def collection(self, name: str) -> "MockCollectionRef":
        return MockCollectionRef(self._store, self._path + [name])

    # -- read / write ------------------------------------------------------

    def _get_node(self) -> Tuple[Dict, str]:
        """Walk *_store* to the parent container and return (parent, key)."""
        node = self._store
        for part in self._path[:-1]:
            node = node.setdefault(part, {})
        return node, self._path[-1]

    def set(self, data: Dict, merge: bool = False) -> None:
        parent, key = self._get_node()
        bucket = parent.setdefault(key, {})
        if merge:
            existing = bucket.get("_fields", {})
            existing.update(copy.deepcopy(data))
            bucket["_fields"] = existing
        else:
            bucket["_fields"] = copy.deepcopy(data)

    def get(self) -> MockDocumentSnapshot:
        parent, key = self._get_node()
        bucket = parent.get(key, {})
        fields = bucket.get("_fields")
        return MockDocumentSnapshot(key, copy.deepcopy(fields) if fields is not None else None, self)

    def delete(self) -> None:
        parent, key = self._get_node()
        bucket = parent.get(key, {})
        bucket.pop("_fields", None)
        # Keep sub-collections intact (Firestore semantics)


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------

_OPS = {
    "==": operator.eq,
    ">=": operator.ge,
    "<": operator.lt,
    ">": operator.gt,
    "<=": operator.le,
    "!=": operator.ne,
}


class MockQuery:
    """Chainable query object."""

    def __init__(self, docs: List[Tuple[str, Dict]], store: Dict = None, col_path: List[str] = None):
        # docs is a list of (doc_id, fields_dict)
        self._docs = list(docs)
        self._store = store
        self._col_path = col_path or []
        self._filters: List[Tuple[str, str, Any]] = []
        self._order_field: Optional[str] = None
        self._order_dir: str = "ASCENDING"
        self._limit_n: Optional[int] = None

    # ---- chaining --------------------------------------------------------

    def where(self, field: str, op: str, value: Any) -> "MockQuery":
        clone = self._clone()
        clone._filters.append((field, op, value))
        return clone

    def order_by(self, field: str, direction: str = "ASCENDING") -> "MockQuery":
        clone = self._clone()
        clone._order_field = field
        clone._order_dir = direction
        return clone

    def limit(self, n: int) -> "MockQuery":
        clone = self._clone()
        clone._limit_n = n
        return clone

    # ---- execution -------------------------------------------------------

    def stream(self):
        results = list(self._docs)

        # Apply filters
        for field, op_str, value in self._filters:
            op_fn = _OPS.get(op_str)
            if op_fn is None:
                raise ValueError(f"Unsupported operator: {op_str}")
            filtered = []
            for doc_id, fields in results:
                doc_val = fields.get(field)
                if doc_val is None:
                    continue
                try:
                    if op_fn(doc_val, value):
                        filtered.append((doc_id, fields))
                except TypeError:
                    continue
            results = filtered

        # Order
        if self._order_field is not None:
            reverse = self._order_dir.upper() == "DESCENDING"
            results.sort(
                key=lambda x: (x[1].get(self._order_field) is None, x[1].get(self._order_field, "")),
                reverse=reverse,
            )

        # Limit
        if self._limit_n is not None:
            results = results[: self._limit_n]

        # Yield snapshots with real refs that can mutate the store
        for doc_id, fields in results:
            if self._store is not None and self._col_path:
                ref = MockDocumentRef(self._store, self._col_path + [doc_id])
            else:
                ref = _SnapshotRef(doc_id)
            yield MockDocumentSnapshot(doc_id, copy.deepcopy(fields), ref)

    # ---- internals -------------------------------------------------------

    def _clone(self) -> "MockQuery":
        q = MockQuery(self._docs, self._store, self._col_path)
        q._filters = list(self._filters)
        q._order_field = self._order_field
        q._order_dir = self._order_dir
        q._limit_n = self._limit_n
        return q


class _SnapshotRef:
    """Fallback ref when store/path are unavailable."""

    def __init__(self, doc_id: str):
        self.id = doc_id

    def delete(self):
        pass


# ---------------------------------------------------------------------------
# Collection reference
# ---------------------------------------------------------------------------

class MockCollectionRef:
    def __init__(self, store: Dict, path: List[str]):
        self._store = store
        self._path = path  # e.g. ["users", "abc", "transactions"]

    def _get_container(self) -> Dict:
        node = self._store
        for part in self._path:
            node = node.setdefault(part, {})
        return node

    # -- navigation --------------------------------------------------------

    def document(self, doc_id: str) -> MockDocumentRef:
        return MockDocumentRef(self._store, self._path + [doc_id])

    def add(self, data: Dict) -> Tuple[Any, MockDocumentRef]:
        doc_id = str(uuid.uuid4())[:8]
        ref = self.document(doc_id)
        ref.set(data)
        return None, ref

    # -- querying ----------------------------------------------------------

    def _all_docs(self) -> List[Tuple[str, Dict]]:
        container = self._get_container()
        results = []
        for key, value in container.items():
            if isinstance(value, dict) and "_fields" in value:
                results.append((key, copy.deepcopy(value["_fields"])))
        return results

    def where(self, field: str, op: str, value: Any) -> MockQuery:
        return MockQuery(self._all_docs(), self._store, self._path).where(field, op, value)

    def order_by(self, field: str, direction: str = "ASCENDING") -> MockQuery:
        return MockQuery(self._all_docs(), self._store, self._path).order_by(field, direction)

    def limit(self, n: int) -> MockQuery:
        return MockQuery(self._all_docs(), self._store, self._path).limit(n)

    def stream(self):
        """Yield all documents in this collection."""
        container = self._get_container()
        for key, value in list(container.items()):
            if isinstance(value, dict) and "_fields" in value:
                ref = MockDocumentRef(self._store, self._path + [key])
                yield MockDocumentSnapshot(key, copy.deepcopy(value["_fields"]), ref)


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------

class MockBatch:
    def __init__(self, store: Dict):
        self._store = store
        self._ops: List[Tuple[str, Any]] = []

    def set(self, ref: MockDocumentRef, data: Dict, merge: bool = False) -> None:
        self._ops.append(("set", ref, data, merge))

    def delete(self, ref) -> None:
        self._ops.append(("delete", ref))

    def commit(self) -> None:
        for op in self._ops:
            if op[0] == "set":
                _, ref, data, merge = op
                ref.set(data, merge=merge)
            elif op[0] == "delete":
                _, ref = op
                ref.delete()
        self._ops.clear()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class MockFirestoreClient:
    """Top-level Firestore client mock backed by an in-memory dict."""

    def __init__(self):
        self._store: Dict = {}

    def collection(self, name: str) -> MockCollectionRef:
        return MockCollectionRef(self._store, [name])

    def batch(self) -> MockBatch:
        return MockBatch(self._store)
