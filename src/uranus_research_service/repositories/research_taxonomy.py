"""Shared authoritative public taxonomy projections, including localized labels."""

from uranus_research_service.repositories.research import DATE_STATUS, GENRE_LABELS, PUBLIC

PUBLIC_EVENT = f"""e.release_status::text IN {PUBLIC} AND (
    NOT EXISTS(SELECT 1 FROM uranus.event_date d WHERE d.event_uuid=e.uuid)
    OR EXISTS(SELECT 1 FROM uranus.event_date d WHERE d.event_uuid=e.uuid
        AND {DATE_STATUS} IN {PUBLIC}))"""

# Canonical labels and public event eligibility shared with semantic indexing.
GENRES_SQL = f"""WITH genres AS ({GENRE_LABELS})
    SELECT g.type_id::text || ':' || g.genre_id::text id,g.name label,g.name name
    FROM genres g WHERE g.genre_id<>0
    AND EXISTS (SELECT 1 FROM uranus.event_type_link l
        JOIN uranus.event e ON e.uuid=l.event_uuid
        WHERE l.type_id=g.type_id AND l.genre_id=g.genre_id AND {PUBLIC_EVENT})
"""


EVENT_TYPES_SQL = f"""WITH types AS (
    SELECT DISTINCT ON(type_id) type_id,name FROM uranus.event_type
    WHERE NULLIF(trim(name),'') IS NOT NULL
    ORDER BY type_id,CASE iso_639_1 WHEN 'de' THEN 0 WHEN 'en' THEN 1 ELSE 2 END,
        iso_639_1 COLLATE "C" NULLS LAST,name COLLATE "C"
)
    SELECT t.type_id::text id,t.name label,t.name name FROM types t
    WHERE EXISTS (SELECT 1 FROM uranus.event_type_link l
        JOIN uranus.event e ON e.uuid=l.event_uuid
        WHERE l.type_id=t.type_id AND {PUBLIC_EVENT})
"""
