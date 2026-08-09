import pytest

from memory import CallerStore, new_caller_id


@pytest.fixture()
def store(tmp_path) -> CallerStore:
    return CallerStore(db_path=str(tmp_path / "memory.db"))


def test_get_unknown_returns_none(store: CallerStore) -> None:
    assert store.get("nobody") is None


def test_upsert_then_get(store: CallerStore) -> None:
    caller_id = new_caller_id()
    profile = store.upsert(
        {
            "caller_id": caller_id,
            "name": "Sunita Devi",
            "location": "Gorakhpur",
            "conditions": ["diabetes"],
        }
    )
    assert profile["name"] == "Sunita Devi"
    assert profile["conditions"] == ["diabetes"]
    assert profile["last_called_at"]

    stored = store.get(caller_id)
    assert stored["name"] == "Sunita Devi"
    assert stored["conditions"] == ["diabetes"]
    assert stored["medications"] == []


def test_upsert_merges_partial_update(store: CallerStore) -> None:
    caller_id = new_caller_id()
    store.upsert({"caller_id": caller_id, "name": "Ravi", "location": "Raipur"})
    updated = store.upsert({"caller_id": caller_id, "medications": ["metformin"]})
    assert updated["name"] == "Ravi"
    assert updated["location"] == "Raipur"
    assert updated["medications"] == ["metformin"]


def test_upsert_deduplicates_list_fields(store: CallerStore) -> None:
    caller_id = new_caller_id()
    store.upsert(
        {"caller_id": caller_id, "conditions": ["asthma", "asthma", "diabetes"]}
    )
    assert store.get(caller_id)["conditions"] == ["asthma", "diabetes"]


def test_delete(store: CallerStore) -> None:
    caller_id = new_caller_id()
    store.upsert({"caller_id": caller_id, "name": "Priya"})
    assert store.delete(caller_id) is True
    assert store.delete(caller_id) is False
    assert store.get(caller_id) is None


def test_list_and_count(store: CallerStore) -> None:
    store.upsert({"caller_id": new_caller_id(), "name": "A"})
    store.upsert({"caller_id": new_caller_id(), "name": "B"})
    assert store.count() == 2
    assert {c["name"] for c in store.list()} == {"A", "B"}


def test_new_caller_id_is_unique() -> None:
    ids = {new_caller_id() for _ in range(100)}
    assert len(ids) == 100
