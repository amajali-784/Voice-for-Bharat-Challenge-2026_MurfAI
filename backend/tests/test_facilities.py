import pytest

import facilities


@pytest.mark.asyncio
async def test_haversine_km_delhi_agra() -> None:
    # Delhi -> Agra is ~178 km by great-circle.  Tolerance covers rounding.
    dist = facilities.haversine_km(28.6139, 77.2090, 27.1767, 78.0081)
    assert 170 < dist < 185


def test_local_facility_search_hindi_alias() -> None:
    result = facilities.local_facility_search("नई दिल्ली")
    assert result is not None
    assert result["status"] == "ok"
    assert result["source"] == "local"
    assert result["data_as_of"]
    assert any("AIIMS" in f["name"] for f in result["facilities"])


def test_local_facility_search_english_alias() -> None:
    result = facilities.local_facility_search("Gurgaon")
    assert result is not None
    assert result["status"] == "ok"
    assert result["query_location"] == "Gurugram"


def test_local_facility_search_unknown_place_returns_none() -> None:
    assert facilities.local_facility_search("some nonexistent village xyz") is None


def test_local_facility_search_filters_by_type() -> None:
    result = facilities.local_facility_search("New Delhi", "pharmacy")
    assert result is not None
    assert result["status"] == "not_found"
    assert result["facilities"] == []


def test_score_elements_sorts_and_deduplicates() -> None:
    elements = [
        {
            "type": "node",
            "lat": 28.6,
            "lon": 77.2,
            "tags": {"name": "B", "amenity": "hospital"},
        },
        {
            "type": "node",
            "lat": 28.65,
            "lon": 77.25,
            "tags": {"name": "A", "amenity": "hospital"},
        },
        {
            "type": "node",
            "lat": 28.6,
            "lon": 77.2,
            "tags": {"name": "B", "amenity": "hospital"},
        },
        {
            "type": "way",
            "center": {"lat": 28.61, "lon": 77.21},
            "tags": {"name": "C", "amenity": "doctors"},
        },
        {"type": "way", "tags": {"name": "No center, skipped"}},
        {
            "type": "node",
            "lat": 28.6,
            "lon": 77.2,
            "tags": {"amenity": "hospital"},
        },  # no name
    ]
    scored = facilities._score_elements(elements, 28.6139, 77.2090)
    assert [f["name"] for f in scored] == ["C", "B", "A"]
    assert (
        scored[0]["distance_km"] < scored[1]["distance_km"] < scored[2]["distance_km"]
    )
    assert scored[0]["type"] == "doctor"  # C is a doctor's clinic and closest
    assert scored[1]["type"] == "hospital"


@pytest.mark.asyncio
async def test_lookup_live_path(monkeypatch) -> None:
    async def fake_geocode(location: str) -> dict:
        return {"lat": 25.3176, "lon": 82.9739, "display_name": "Varanasi, UP, India"}

    async def fake_fetch(lat, lon, radius_km, facility_type) -> list:
        return [
            {
                "name": "BHU Hospital",
                "type": "hospital",
                "distance_km": 3.2,
                "address": "Varanasi",
            },
            {
                "name": "DDU Hospital",
                "type": "hospital",
                "distance_km": 4.1,
                "address": "Varanasi",
            },
        ]

    monkeypatch.setattr(facilities, "geocode_place", fake_geocode)
    monkeypatch.setattr(facilities, "fetch_nearby_osm", fake_fetch)

    result = await facilities.lookup_health_facilities("Varanasi")
    assert result["status"] == "ok"
    assert result["source"] == "live"
    assert result["data_as_of"]
    assert result["query_location"] == "Varanasi, UP, India"
    assert len(result["facilities"]) == 2


@pytest.mark.asyncio
async def test_lookup_live_not_found(monkeypatch) -> None:
    async def fake_geocode(location: str) -> dict:
        return {"lat": 25.3176, "lon": 82.9739, "display_name": "Varanasi, UP, India"}

    async def fake_fetch(lat, lon, radius_km, facility_type) -> list:
        return []

    monkeypatch.setattr(facilities, "geocode_place", fake_geocode)
    monkeypatch.setattr(facilities, "fetch_nearby_osm", fake_fetch)

    result = await facilities.lookup_health_facilities("Varanasi")
    assert result["status"] == "not_found"
    assert result["source"] == "live"


@pytest.mark.asyncio
async def test_lookup_falls_back_to_local_when_live_down(monkeypatch) -> None:
    async def broken_geocode(location: str) -> dict:
        raise facilities.httpx.ConnectError("network down")

    monkeypatch.setattr(facilities, "geocode_place", broken_geocode)

    result = await facilities.lookup_health_facilities("नई दिल्ली")
    assert result["status"] == "ok"
    assert result["source"] == "local"
    assert any("AIIMS" in f["name"] for f in result["facilities"])


@pytest.mark.asyncio
async def test_lookup_unavailable_when_everything_down(monkeypatch) -> None:
    async def broken_geocode(location: str) -> dict:
        raise facilities.httpx.ConnectError("network down")

    monkeypatch.setattr(facilities, "geocode_place", broken_geocode)

    result = await facilities.lookup_health_facilities("Mumbaiwadi remote village")
    assert result["status"] == "unavailable"
    assert result["source"] == "none"
    assert result["facilities"] == []


@pytest.mark.asyncio
async def test_lookup_invalid_facility_type_defaults_to_hospital(monkeypatch) -> None:
    captured: dict = {}

    async def fake_geocode(location: str) -> dict:
        return {"lat": 25.3176, "lon": 82.9739, "display_name": "Varanasi"}

    async def fake_fetch(lat, lon, radius_km, facility_type) -> list:
        captured["facility_type"] = facility_type
        return []

    monkeypatch.setattr(facilities, "geocode_place", fake_geocode)
    monkeypatch.setattr(facilities, "fetch_nearby_osm", fake_fetch)

    await facilities.lookup_health_facilities("Varanasi", "bogus-type")
    assert captured["facility_type"] == "hospital"
