"""Self-reported participant data, separate from stimulus metadata."""

DEMOGRAPHIC_FIELDS = ("participant_gender", "participant_age", "participant_education")
PARTICIPANT_COLUMNS = ("participant_id", "session_id", *DEMOGRAPHIC_FIELDS, "demographics_submitted_at")
GENDER_OPTIONS = {"woman": "Donna", "man": "Uomo", "non_binary": "Non binario",
                  "other": "Altro", "prefer_not_to_say": "Preferisco non rispondere"}
EDUCATION_OPTIONS = {"high_school": "Diploma di scuola superiore", "bachelor": "Laurea triennale",
                     "master": "Laurea magistrale", "doctorate": "Dottorato di ricerca",
                     "other": "Altro / nessuno di questi", "prefer_not_to_say": "Preferisco non rispondere"}


def validate_demographics(gender, age, education):
    if (not isinstance(gender, str) or gender not in GENDER_OPTIONS
            or not isinstance(education, str) or education not in EDUCATION_OPTIONS
            or type(age) is not int or age < 0):
        raise ValueError("Completa i tre campi. Indica l'età in anni compiuti.")
    return dict(zip(DEMOGRAPHIC_FIELDS, (gender, age, education)))


def demographic_values(event):
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    return {field: event.get(field, details.get(field, "")) for field in DEMOGRAPHIC_FIELDS}


def participant_rows(events):
    rows = {}
    for event in events:
        if event.get("event_type") != "demographics_submitted":
            continue
        key = (event.get("participant_id", ""), event.get("session_id", ""))
        rows.setdefault(key, {"participant_id": key[0], "session_id": key[1],
                              **demographic_values(event),
                              "demographics_submitted_at": event.get("server_received_ts", "")})
    return list(rows.values())
