"""Freshly invented English policies for a fictional team, never real records."""

from __future__ import annotations

from copy import deepcopy

CASE_IDS = ("supported", "insufficient", "untrusted", "restricted")

CASES = {
    "supported": {
        "title": "Question with an eligible source",
        "question": "What are the support hours for team Narkis?",
    },
    "insufficient": {
        "title": "Question without evidence",
        "question": "What is the weather forecast for Haifa tomorrow?",
    },
    "untrusted": {
        "title": "Matching source is untrusted",
        "question": "What is the equipment reimbursement limit for team Narkis?",
    },
    "restricted": {
        "title": "Matching source is restricted by showcase policy",
        "question": "Who holds laboratory room access for team Narkis?",
    },
}

_DOCUMENTS = (
    {
        "id": "support-hours",
        "title": "Support hours policy",
        "text": "The support hours for team Narkis are Sunday through Thursday from 18:00 to 21:00.",
        "sourceUri": "fixture://narkis/support-hours",
        "trust": "trusted",
        "sensitivity": 0.0,
    },
    {
        "id": "request-channel",
        "title": "Request channel policy",
        "text": "Requests to team Narkis use the demo form and are handled the following evening.",
        "sourceUri": "fixture://narkis/request-channel",
        "trust": "trusted",
        "sensitivity": 0.0,
    },
    {
        "id": "equipment-draft",
        "title": "Unreviewed equipment draft",
        "text": "The equipment reimbursement limit for team Narkis is 450 shekels under an unreviewed draft.",
        "sourceUri": "fixture://narkis/equipment-draft",
        "trust": "untrusted",
        "sensitivity": 0.0,
    },
    {
        "id": "room-access",
        "title": "Laboratory room access policy",
        "text": "Fictional team Pomegranate holds laboratory room access for team Narkis.",
        "sourceUri": "fixture://narkis/room-access",
        "trust": "trusted",
        "sensitivity": 1.0,
    },
)


def get_documents() -> list[dict[str, object]]:
    """Return detached synthetic records so callers cannot alter future runs."""
    return deepcopy(list(_DOCUMENTS))
