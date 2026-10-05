"""Synthetic complete area inventory; no live geocoder or production polygons."""

import json


def place(name, identity, west):
    return dict(
        name=name,
        display_name=name,
        osm_type="relation",
        osm_id=identity,
        administrative_level="municipality",
        administrative_levels=["municipality"],
        country_code="de",
        boundary=dict(
            type="Polygon",
            coordinates=[[[west, 54], [west + 1, 54], [west + 1, 55], [west, 55], [west, 54]]],
        ),
    )


PLACES = [place("Flensburg", 1, 9), place("Glücksburg", 2, 10)]
CATALOG = {
    "catalogs": [
        {
            "schema_version": "administrative-catalog-v1",
            "level": "municipality",
            "parent_area_id": None,
            "country_codes": ["de"],
            "complete": True,
            "inventory_source": "synthetic phase2 fixture",
            "items": PLACES,
        }
    ]
}


def geocoder_reply(request):
    import httpx

    if request.url.path == "/ready":
        return httpx.Response(200, json={"status": "ready"})
    payload = json.loads(request.content)
    if request.url.path == "/lookup":
        return httpx.Response(200, json=next(p for p in PLACES if p["osm_id"] == payload["osm_id"]))
    if request.url.path == "/search":
        return httpx.Response(
            200,
            json={
                "query": payload["query"],
                "items": [p for p in PLACES if p["name"] == payload["query"]],
            },
        )
    raise AssertionError("Unexpected geocoder path")
