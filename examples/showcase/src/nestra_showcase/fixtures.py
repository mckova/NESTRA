"""Freshly invented Hebrew policies for a fictional team, never real records."""

from __future__ import annotations

from copy import deepcopy

CASE_IDS = ("supported", "insufficient", "untrusted", "restricted")

CASES = {
    "supported": {
        "title": "שאלה עם מקור מורשה",
        "question": "מה שעות התמיכה בצוות נרקיס?",
    },
    "insufficient": {
        "title": "שאלה ללא ראיות",
        "question": "מה תחזית מזג האוויר בחיפה מחר?",
    },
    "untrusted": {
        "title": "מקור שאינו מהימן",
        "question": "מה תקרת ההחזר לציוד בצוות נרקיס?",
    },
    "restricted": {
        "title": "מקור שאסור להצגה במדיניות הדמו",
        "question": "מי מחזיקי הרשאת חדר ניסוי בצוות נרקיס?",
    },
}

_DOCUMENTS = (
    {
        "id": "support-hours",
        "title": "שעות תמיכה",
        "text": "שעות התמיכה בצוות נרקיס הן בימים ראשון עד חמישי, בין 18:00 ל־21:00.",
        "sourceUri": "fixture://narkis/support-hours",
        "trust": "trusted",
        "sensitivity": 0.0,
    },
    {
        "id": "request-channel",
        "title": "ערוץ פניות",
        "text": "פניות לצוות נרקיס נשלחות דרך טופס הדמו ומטופלות בערב הבא.",
        "sourceUri": "fixture://narkis/request-channel",
        "trust": "trusted",
        "sensitivity": 0.0,
    },
    {
        "id": "equipment-draft",
        "title": "טיוטת החזר ציוד",
        "text": "תקרת ההחזר לציוד בצוות נרקיס היא 450 שקלים לפי טיוטה שלא נבדקה.",
        "sourceUri": "fixture://narkis/equipment-draft",
        "trust": "untrusted",
        "sensitivity": 0.0,
    },
    {
        "id": "room-access",
        "title": "הרשאות חדר ניסוי",
        "text": "מחזיקי הרשאת חדר ניסוי בצוות נרקיס הם חברי צוות רימון הפיקטיבי.",
        "sourceUri": "fixture://narkis/room-access",
        "trust": "trusted",
        "sensitivity": 1.0,
    },
)


def get_documents() -> list[dict[str, object]]:
    """Return detached synthetic records so callers cannot alter future runs."""
    return deepcopy(list(_DOCUMENTS))
