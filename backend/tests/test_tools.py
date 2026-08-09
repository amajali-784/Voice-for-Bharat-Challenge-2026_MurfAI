import pytest
from livekit.agents import RunContext

from agent import Assistant
from memory import CallerStore, new_caller_id


class _FakeSpeechHandle:
    num_steps = 1


class _FakeSession:
    def __init__(self, userdata: dict) -> None:
        self.userdata = userdata


def _make_ctx(userdata: dict) -> RunContext:
    return RunContext(
        session=_FakeSession(userdata),
        speech_handle=_FakeSpeechHandle(),
        function_call=None,
    )


@pytest.fixture()
def caller_id() -> str:
    return new_caller_id()


@pytest.fixture()
def store(tmp_path) -> CallerStore:
    return CallerStore(db_path=str(tmp_path / "memory.db"))


@pytest.mark.asyncio
async def test_lookup_unknown_caller(store: CallerStore, caller_id: str) -> None:
    ctx = _make_ctx({"caller_id": caller_id, "store": store})
    result = await Assistant().lookup_caller(ctx)
    assert result["known"] is False


@pytest.mark.asyncio
async def test_save_then_lookup(store: CallerStore, caller_id: str) -> None:
    agent = Assistant()
    ctx = _make_ctx({"caller_id": caller_id, "store": store})

    await agent.save_caller_info(
        ctx,
        name="Sunita Devi",
        location="Gorakhpur",
        conditions=["diabetes"],
        medications=["metformin"],
    )

    profile = store.get(caller_id)
    assert profile["name"] == "Sunita Devi"
    assert profile["conditions"] == ["diabetes"]
    assert profile["medications"] == ["metformin"]

    result = await agent.lookup_caller(ctx)
    assert result["known"] is True
    assert result["name"] == "Sunita Devi"


@pytest.mark.asyncio
async def test_save_does_not_wipe_known_fields(
    store: CallerStore, caller_id: str
) -> None:
    agent = Assistant()
    ctx = _make_ctx({"caller_id": caller_id, "store": store})

    await agent.save_caller_info(ctx, name="Ravi", location="Raipur")
    await agent.save_caller_info(ctx, medications=["metformin"])

    stored = store.get(caller_id)
    assert stored["name"] == "Ravi"
    assert stored["location"] == "Raipur"
    assert stored["medications"] == ["metformin"]


@pytest.mark.asyncio
async def test_add_note(store: CallerStore, caller_id: str) -> None:
    ctx = _make_ctx({"caller_id": caller_id, "store": store})
    await Assistant().add_note(ctx, "follow-up needed")
    assert store.get(caller_id)["notes"] == ["follow-up needed"]


@pytest.mark.asyncio
async def test_forget_caller(store: CallerStore, caller_id: str) -> None:
    agent = Assistant()
    ctx = _make_ctx({"caller_id": caller_id, "store": store})
    await agent.save_caller_info(ctx, name="Priya")

    result = await agent.forget_caller(ctx)
    assert result["forgotten"] is True
    assert store.get(caller_id) is None


@pytest.mark.asyncio
async def test_find_nearby_health_facilities_calls_lookup(
    monkeypatch, store: CallerStore, caller_id: str
) -> None:
    """Day 5: the tool method should hand the location to the lookup and return
    whatever it says — including a graceful 'unavailable' result."""
    captured: dict = {}

    async def fake_lookup(location: str, facility_type: str = "hospital") -> dict:
        captured["location"] = location
        captured["facility_type"] = facility_type
        return {
            "status": "ok",
            "source": "local",
            "data_as_of": "2026-08-09T00:00:00Z",
            "facilities": [
                {
                    "name": "Sir Sunderlal Hospital BHU",
                    "type": "hospital",
                    "address": "BHU Campus, Varanasi",
                }
            ],
        }

    monkeypatch.setattr("agent.lookup_health_facilities", fake_lookup)
    ctx = _make_ctx({"caller_id": caller_id, "store": store})

    result = await Assistant().find_nearby_health_facilities(ctx, "Varanasi")
    assert result["status"] == "ok"
    assert captured["location"] == "Varanasi"
    assert captured["facility_type"] == "hospital"


@pytest.mark.asyncio
async def test_find_nearby_health_facilities_unavailable_is_passed_through(
    monkeypatch, store: CallerStore, caller_id: str
) -> None:
    async def fake_lookup(location: str, facility_type: str = "hospital") -> dict:
        return {
            "status": "unavailable",
            "source": "none",
            "facilities": [],
            "message": "The live health-facility data source could not be reached.",
        }

    monkeypatch.setattr("agent.lookup_health_facilities", fake_lookup)
    ctx = _make_ctx({"caller_id": caller_id, "store": store})

    result = await Assistant().find_nearby_health_facilities(ctx, "Delhi")
    assert result["status"] == "unavailable"
    assert result["facilities"] == []
