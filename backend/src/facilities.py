"""Nearby health-facility lookup for the Swasthya Sahayak voice agent.

Day 5: the agent can now answer "हमारे यहाँ नज़दीकी अस्पताल कहाँ है?" with real
data instead of only a generic "ask your ASHA worker".

Data sources, in order of preference:

1. **Live — OpenStreetMap** (default). The caller's village/town/district is
   geocoded with the Nominatim API (restricted to ``countrycodes=in``), then
   nearby facilities are pulled from the Overpass API. Free, keyless, live.
   If either endpoint is unreachable, slow, or the place cannot be geocoded,
   we fall back to step 2.

2. **Local — curated offline list** (:data:`LOCAL_FACILITIES`). A small
   hand-built subset of well-known public hospitals for a few major districts,
   so the agent still gives a helpful, honest answer when the network is down.
   This is NOT exhaustive and is clearly labelled as ``source="local"``.

Every result carries a ``source`` ("live" | "local" | "none") and a
``data_as_of`` timestamp so the agent can say *when* the data is from instead
of pretending it is always fresh.  On total failure it returns
``status="unavailable"`` with a helpful message — it never fabricates a
facility name, distance or phone number.

To demo the failure path, set ``FACILITIES_NOMINATIM_URL`` or
``FACILITIES_OVERPASS_URL`` to an unreachable URL.  Overpass mirrors can be
overridden with a comma-separated ``FACILITIES_OVERPASS_URLS``.
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import re
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("health-access-facilities")

# ---------------------------------------------------------------------------
# Endpoints (overridable for testing and for demoing the failure path).
# Point FACILITIES_NOMINATIM_URL / FACILITIES_OVERPASS_URL at an unreachable
# host to see the agent's graceful spoken fallback.  Overpass has several
# public mirrors; they are tried in order until one answers.
# ---------------------------------------------------------------------------
NOMINATIM_URL = os.getenv(
    "FACILITIES_NOMINATIM_URL", "https://nominatim.openstreetmap.org/search"
)

_DEFAULT_OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def _overpass_endpoints() -> list[str]:
    env = os.getenv("FACILITIES_OVERPASS_URLS") or os.getenv("FACILITIES_OVERPASS_URL")
    if env:
        return [u.strip() for u in env.split(",") if u.strip()]
    return list(_DEFAULT_OVERPASS_ENDPOINTS)


_USER_AGENT = "SwasthyaSahayak/1.0 (VoiceForBharat; contact via Murf challenge)"

# Time budgets for the live path — a caller is waiting on the phone.
GEOCODE_TIMEOUT = 5.0
OVERPASS_TIMEOUT = 7.0
LIVE_TOTAL_BUDGET = 16.0

DEFAULT_RADIUS_KM = 12.0
MAX_RESULTS = 5

_EARTH_RADIUS_KM = 6371.0

# ---------------------------------------------------------------------------
# Facility type mapping (tool-facing value -> OSM amenity values).
# ---------------------------------------------------------------------------
_FACILITY_TYPES = {
    "hospital": ["hospital"],
    "clinic": ["clinic", "doctors"],
    "doctor": ["doctors", "clinic"],
    "pharmacy": ["pharmacy"],
    "any": ["hospital", "clinic", "doctors", "pharmacy"],
}

_FRIENDLY_TYPE = {
    "hospital": "hospital",
    "clinic": "clinic",
    "doctors": "doctor",
    "pharmacy": "pharmacy",
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two lat/lon points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    )
    return _EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def geocode_place(location: str) -> dict | None:
    """Geocode an Indian place name with Nominatim.

    Returns ``{lat, lon, display_name}`` or ``None`` if nothing was found.
    Raises on transport/HTTP errors so the caller can decide the fallback.
    """
    params = {
        "q": location,
        "format": "json",
        "limit": 1,
        "countrycodes": "in",
    }
    async with httpx.AsyncClient(
        timeout=GEOCODE_TIMEOUT, headers={"User-Agent": _USER_AGENT}
    ) as client:
        response = await client.get(NOMINATIM_URL, params=params)
        response.raise_for_status()
        data = response.json()
    if not data:
        return None
    first = data[0]
    return {
        "lat": float(first["lat"]),
        "lon": float(first["lon"]),
        "display_name": first.get("display_name"),
    }


async def fetch_nearby_osm(
    lat: float,
    lon: float,
    radius_km: float = DEFAULT_RADIUS_KM,
    facility_type: str = "hospital",
) -> list[dict]:
    """Query the Overpass API for health facilities within ``radius_km``.

    Returns a flat list of ``{name, type, distance_km, address, phone}`` dicts,
    nearest first, deduplicated by name. Raises on transport/HTTP errors.
    """
    radius_m = int(radius_km * 1000)
    amenities = _FACILITY_TYPES.get(facility_type, _FACILITY_TYPES["hospital"])
    amenity_re = "|".join(amenities)
    query = f"""
    [out:json][timeout:{int(OVERPASS_TIMEOUT)}];
    (
      node["amenity"~"^({amenity_re})$"](around:{radius_m},{lat},{lon});
      way["amenity"~"^({amenity_re})$"](around:{radius_m},{lat},{lon});
    );
    out center tags 100;
    """
    endpoints = _overpass_endpoints()
    last_error: Exception | None = None
    for endpoint in endpoints:
        try:
            async with httpx.AsyncClient(
                timeout=OVERPASS_TIMEOUT, headers={"User-Agent": _USER_AGENT}
            ) as client:
                response = await client.post(endpoint, data={"data": query})
                response.raise_for_status()
                data = response.json()
            break
        except Exception as exc:
            last_error = exc
            logger.warning("overpass mirror %s failed: %s", endpoint, exc)
    else:
        raise last_error or httpx.TransportError("no overpass endpoint configured")

    facilities = _score_elements(data.get("elements", []), lat, lon)
    return facilities[:MAX_RESULTS]


def _score_elements(elements: list, lat: float, lon: float) -> list[dict]:
    """Turn raw Overpass elements into scored, deduplicated facility dicts."""
    scored: list[dict] = []
    seen: set[str] = set()
    for element in elements:
        tags = element.get("tags") or {}
        name = tags.get("name")
        if not name:
            continue
        key = name.strip().lower()
        if key in seen:
            continue
        if element.get("type") == "node":
            elat, elon = element.get("lat"), element.get("lon")
        else:
            center = element.get("center") or {}
            elat, elon = center.get("lat"), center.get("lon")
        if elat is None or elon is None:
            continue
        distance = haversine_km(lat, lon, float(elat), float(elon))
        seen.add(key)
        scored.append(
            {
                "name": name.strip(),
                "type": _FRIENDLY_TYPE.get(tags.get("amenity"), tags.get("amenity")),
                "distance_km": round(distance, 1),
                "address": _join_address(tags),
                "phone": tags.get("phone") or tags.get("contact:phone") or None,
            }
        )
    scored.sort(key=lambda f: f["distance_km"])
    return scored


def _join_address(tags: dict) -> str | None:
    """Best-effort address from OSM tags; ``None`` when we know nothing."""
    parts = [
        tags.get("addr:full"),
        tags.get("addr:street"),
        tags.get("addr:district"),
        tags.get("addr:city"),
        tags.get("addr:state"),
    ]
    parts = [p for p in parts if p]
    return ", ".join(dict.fromkeys(parts)) if parts else None


# ---------------------------------------------------------------------------
# Local (offline) fallback — clearly curated, NOT exhaustive.
# Well-known public hospitals for a few major districts, with name/type/address
# only. No phone numbers or distances are invented here; the agent should say
# the data is from its saved offline list when it uses it.
# ---------------------------------------------------------------------------
LOCAL_LAST_UPDATED = "2026-08-09T00:00:00Z"

LOCAL_FACILITIES: dict[str, list[dict]] = {
    "new delhi": [
        {
            "name": "All India Institute of Medical Sciences (AIIMS)",
            "type": "hospital",
            "address": "Ansari Nagar, New Delhi",
        },
        {
            "name": "Lok Nayak Hospital (LNJP)",
            "type": "hospital",
            "address": "Jawaharlal Nehru Marg, New Delhi",
        },
        {
            "name": "Safdarjung Hospital",
            "type": "hospital",
            "address": "Ring Road, New Delhi",
        },
    ],
    "gurugram": [
        {
            "name": "Civil Hospital Gurugram",
            "type": "hospital",
            "address": "Sector 10, Gurugram, Haryana",
        },
        {
            "name": "ESI Hospital Gurugram",
            "type": "hospital",
            "address": "Sector 15, Gurugram, Haryana",
        },
    ],
    "noida": [
        {
            "name": "District Hospital Noida (Pratap Vihar)",
            "type": "hospital",
            "address": "Pratap Vihar, Sector 30, Noida, Uttar Pradesh",
        },
    ],
    "lucknow": [
        {
            "name": "King George's Medical University (KGMU)",
            "type": "hospital",
            "address": "Chowk, Lucknow, Uttar Pradesh",
        },
        {
            "name": "Lok Bandhu Raj Narain Combined Hospital",
            "type": "hospital",
            "address": "Lucknow, Uttar Pradesh",
        },
    ],
    "varanasi": [
        {
            "name": "Sir Sunderlal Hospital, Banaras Hindu University",
            "type": "hospital",
            "address": "BHU Campus, Varanasi, Uttar Pradesh",
        },
        {
            "name": "District Hospital Varanasi (Pandit Deendayal)",
            "type": "hospital",
            "address": "Varanasi, Uttar Pradesh",
        },
    ],
    "jaipur": [
        {
            "name": "Sawai Man Singh Hospital (SMS)",
            "type": "hospital",
            "address": "JLN Marg, Jaipur, Rajasthan",
        },
        {
            "name": "JK Lone Hospital",
            "type": "hospital",
            "address": "SMS Medical College campus, Jaipur, Rajasthan",
        },
    ],
    "mumbai": [
        {
            "name": "KEM Hospital",
            "type": "hospital",
            "address": "Parel, Mumbai, Maharashtra",
        },
        {
            "name": "Sir JJ Hospital",
            "type": "hospital",
            "address": "Byculla, Mumbai, Maharashtra",
        },
        {
            "name": "Nair Hospital",
            "type": "hospital",
            "address": "Mumbai Central, Mumbai, Maharashtra",
        },
    ],
    "pune": [
        {
            "name": "Sassoon General Hospital",
            "type": "hospital",
            "address": "Sassoon Road, Pune, Maharashtra",
        },
    ],
    "bengaluru": [
        {
            "name": "Victoria Hospital",
            "type": "hospital",
            "address": "Fort, Bengaluru, Karnataka",
        },
        {
            "name": "KC General Hospital",
            "type": "hospital",
            "address": "Malleshwaram, Bengaluru, Karnataka",
        },
    ],
    "chennai": [
        {
            "name": "Rajiv Gandhi Government General Hospital",
            "type": "hospital",
            "address": "Park Town, Chennai, Tamil Nadu",
        },
    ],
    "hyderabad": [
        {
            "name": "Gandhi Hospital",
            "type": "hospital",
            "address": "Musheerabad, Secunderabad, Telangana",
        },
        {
            "name": "Osmania General Hospital",
            "type": "hospital",
            "address": "Afzalgunj, Hyderabad, Telangana",
        },
    ],
    "kolkata": [
        {
            "name": "IPGMER and SSKM Hospital",
            "type": "hospital",
            "address": "Bhowanipore, Kolkata, West Bengal",
        },
        {
            "name": "M R Bangur Hospital",
            "type": "hospital",
            "address": "Tollygunge, Kolkata, West Bengal",
        },
    ],
    "patna": [
        {
            "name": "Patna Medical College Hospital (PMCH)",
            "type": "hospital",
            "address": "Ashok Rajpath, Patna, Bihar",
        },
        {
            "name": "AIIMS Patna",
            "type": "hospital",
            "address": "Phulwarisharif, Patna, Bihar",
        },
    ],
    "ahmedabad": [
        {
            "name": "Civil Hospital Ahmedabad",
            "type": "hospital",
            "address": "Asarwa, Ahmedabad, Gujarat",
        },
    ],
    "indore": [
        {
            "name": "Maharaja Yeshwantrao Hospital (MY Hospital)",
            "type": "hospital",
            "address": "Indore, Madhya Pradesh",
        },
    ],
}

# Aliases for the curated list, so Hindi and colloquial names both match.
_LOCATION_ALIASES: dict[str, list[str]] = {
    "new delhi": ["delhi", "दिल्ली", "नई दिल्ली", "dilli", "new-delhi"],
    "gurugram": ["gurgaon", "गुरुग्राम", "गुड़गांव", "गुड़गाँव"],
    "noida": ["नोएडा", "नौएडा"],
    "lucknow": ["लखनऊ"],
    "varanasi": ["बनारस", "काशी", "बनारस"],
    "jaipur": ["जयपुर"],
    "mumbai": ["बम्बई", "मुम्बई", "मुंबई", "bombay"],
    "pune": ["पुणे"],
    "bengaluru": ["bangalore", "बेंगलुरु", "बेंगलूरु"],
    "chennai": ["madras", "मद्रास", "चेन्नई"],
    "hyderabad": ["secunderabad", "हैदराबाद", "हैदराबाद"],
    "kolkata": ["calcutta", "कोलकाता", "कलकत्ता"],
    "patna": ["पटना"],
    "ahmedabad": ["amadavad", "अहमदाबाद"],
    "indore": ["इन्दौर", "इंदौर"],
}


def _canonical_location(location: str) -> str | None:
    """Map a free-form place name to a key in LOCAL_FACILITIES, or ``None``.

    Keeps non-Latin scripts (e.g. Devanagari) intact — the normalizer must not
    strip combining marks.  A single-word alias must match a whole token so
    "mumbaiwadi village" does not match "mumbai"; multi-word aliases may match
    anywhere in the string.
    """
    if not location:
        return None
    query = re.sub(r"\s+", " ", location.lower()).strip()
    if not query:
        return None
    strip_chars = " .,;:'\"()[]{}!?/\\-_"
    tokens = {tok.strip(strip_chars) for tok in query.split() if tok.strip(strip_chars)}
    for canonical, aliases in _LOCATION_ALIASES.items():
        for cand in [canonical, *aliases]:
            if cand not in query:
                continue
            if len(cand.split()) > 1 or cand in tokens:
                return canonical
    return None


def local_facility_search(
    location: str, facility_type: str = "hospital"
) -> dict | None:
    """Search the curated offline list. ``None`` if the place is not covered."""
    canonical = _canonical_location(location)
    if canonical is None:
        return None
    amenities = _FACILITY_TYPES.get(facility_type, _FACILITY_TYPES["hospital"])
    facilities = [
        f for f in LOCAL_FACILITIES.get(canonical, []) if f["type"] in amenities
    ]
    if not facilities:
        return {
            "status": "not_found",
            "source": "local",
            "source_detail": "curated offline list (see README)",
            "data_as_of": LOCAL_LAST_UPDATED,
            "query_location": canonical.title(),
            "facilities": [],
            "message": "No matching facilities in the offline list for this place.",
        }
    return {
        "status": "ok",
        "source": "local",
        "source_detail": "curated offline list (see README)",
        "data_as_of": LOCAL_LAST_UPDATED,
        "query_location": canonical.title(),
        "facilities": facilities,
        "message": "Facilities found in the offline list.",
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def _live_lookup(location: str, facility_type: str) -> dict:
    """Live OpenStreetMap path. Raises if the network/data source fails."""
    geo = await geocode_place(location)
    if not geo:
        raise LookupError(f"Could not geocode location: {location!r}")
    raw = await fetch_nearby_osm(
        geo["lat"], geo["lon"], DEFAULT_RADIUS_KM, facility_type
    )
    if not raw:
        return {
            "status": "not_found",
            "source": "live",
            "source_detail": "OpenStreetMap (Overpass API)",
            "data_as_of": _now_iso(),
            "query_location": geo.get("display_name") or location,
            "facilities": [],
            "message": "No facilities found within the search radius.",
        }
    return {
        "status": "ok",
        "source": "live",
        "source_detail": "OpenStreetMap (Overpass API)",
        "data_as_of": _now_iso(),
        "query_location": geo.get("display_name") or location,
        "facilities": raw,
        "message": "Facilities fetched live from OpenStreetMap.",
    }


def _unavailable(location: str, facility_type: str, reason: str) -> dict:
    return {
        "status": "unavailable",
        "source": "none",
        "source_detail": reason,
        "data_as_of": _now_iso(),
        "query_location": location,
        "facilities": [],
        "message": (
            "The live health-facility data source could not be reached right now. "
            "No facilities were invented. Try again shortly."
        ),
    }


async def lookup_health_facilities(
    location: str, facility_type: str = "hospital"
) -> dict:
    """Fetch nearby health facilities for a place.

    Prefers live OpenStreetMap data; falls back to the curated offline list
    when the network is down; returns ``status="unavailable"`` (never
    fabricated data) if neither works.
    """
    facility_type = (facility_type or "hospital").strip().lower()
    if facility_type not in _FACILITY_TYPES:
        facility_type = "hospital"

    try:
        result = await asyncio.wait_for(
            _live_lookup(location, facility_type), LIVE_TOTAL_BUDGET
        )
        logger.info(
            "facility lookup ok: source=%s location=%r type=%s",
            result["source"],
            location,
            facility_type,
        )
        return result
    except Exception as exc:
        logger.warning(
            "live facility lookup failed for %r (%s): %s",
            location,
            type(exc).__name__,
            exc,
        )

    local = local_facility_search(location, facility_type)
    if local is not None:
        logger.info("facility lookup fell back to local list for %r", location)
        return local

    return _unavailable(
        location, facility_type, "live source down and place not in offline list"
    )
