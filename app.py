"""InstaLab: Instagram-inspired research-feed prototype for Streamlit.

Customize the visual layout in styles.css, interactions in feed.js,
and example posts/stimuli in posts.json. Demo events stay in session only.
"""

from __future__ import annotations

import base64
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

BASE = Path(__file__).resolve().parent
st.set_page_config(
    page_title="InstaLab | Social Feed Simulation",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Remove Streamlit visual chrome so the simulation fills the entire viewport.
st.markdown(
    """
    <style>
      .stApp { background: #fff; }
      header[data-testid="stHeader"] { display: none; }
      #MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }
      .block-container { max-width: none !important; padding: 0 !important; }
      [data-testid="stMainBlockContainer"] { padding: 0 !important; }
      div[data-testid="stVerticalBlock"] { gap: 0 !important; }
      div[data-testid="stElementContainer"] { margin: 0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


def local_image_data(filename: str) -> str:
    """Serve only local JPEG/PNG/WEBP images from the repository root."""
    candidate = BASE / str(filename)
    if candidate.parent != BASE or candidate.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        return ""
    if not candidate.is_file():
        return ""
    mime = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }[candidate.suffix.lower()]
    return f"data:{mime};base64,{base64.b64encode(candidate.read_bytes()).decode('ascii')}"


@st.cache_data(show_spinner=False)
def load_stimuli() -> dict:
    raw = json.loads((BASE / "posts.json").read_text(encoding="utf-8"))
    for post in raw.get("posts", []):
        post["image_url"] = local_image_data(post.get("image", ""))
        post["avatar_url"] = local_image_data(post.get("avatar", post.get("image", "")))
    for story in raw.get("stories", []):
        story["image_url"] = local_image_data(story.get("image", ""))
    return raw


@st.cache_data(show_spinner=False)
def load_frontend() -> tuple[str, str]:
    return (
        (BASE / "styles.css").read_text(encoding="utf-8"),
        (BASE / "feed.js").read_text(encoding="utf-8"),
    )


def export_csv(events: list[dict]) -> bytes:
    stream = io.StringIO()
    columns = ["event_id", "participant_id", "event_type", "post_id",
               "stimulus_id", "stimulus_type", "client_ts", "elapsed_ms", "details"]
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    for event in events:
        writer.writerow({k: (
            json.dumps(event.get(k, {}), ensure_ascii=False) if k == "details"
            else event.get(k, "")
        ) for k in columns})
    return stream.getvalue().encode("utf-8-sig")


study = load_stimuli()
css, js = load_frontend()
participant_id = str(st.query_params.get("PROLIFIC_PID", "DEMO_SESSION"))

if "feed_events" not in st.session_state:
    st.session_state.feed_events = []
    st.session_state.seen_event_ids = set()

feed_component = st.components.v2.component(
    "instalab_social_feed",
    html='<div id="instalab-root" aria-label="Simulazione di social feed"></div>',
    css=css,
    js=js,
    isolate_styles=True,
)

response = feed_component(
    key="instalab_main_feed",
    data={
        "posts": study.get("posts", []),
        "stories": study.get("stories", []),
        "title": study.get("display_name", "InstaLab"),
        "participant_id": participant_id,
        "history": st.session_state.feed_events,
    },
    default={"events": []},
    on_events_change=lambda: None,
    width="stretch",
)

# Store only newly received events (the v2 state contains the cumulative batch).
# No database is configured in this demo: session data disappears after restart.
new_events = response.events or []
for event in new_events:
    if not isinstance(event, dict):
        continue
    event_id = str(event.get("event_id", ""))
    if not event_id or event_id in st.session_state.seen_event_ids:
        continue
    st.session_state.seen_event_ids.add(event_id)
    event = dict(event)
    event["participant_id"] = participant_id
    post = next((p for p in study.get("posts", []) if p.get("id") == event.get("post_id")), None)
    event["stimulus_id"] = post.get("stimulus_id", "") if post else ""
    event["stimulus_type"] = post.get("stimulus_type", "") if post else ""
    event["server_received_ts"] = datetime.now(timezone.utc).isoformat()
    st.session_state.feed_events.append(event)

# Open ?preview=1 to inspect the research log without displaying it to participants.
if str(st.query_params.get("preview", "0")) == "1":
    with st.expander("🔬 Pannello ricercatore — anteprima e log", expanded=True):
        st.caption("I dati di questa versione sono temporanei: non usare per raccolte Prolific reali.")
        st.write(f"Partecipante: {participant_id} · Eventi: {len(st.session_state.feed_events)}")
        st.dataframe(st.session_state.feed_events, use_container_width=True, hide_index=True)
        st.download_button(
            "Scarica interazioni CSV",
            data=export_csv(st.session_state.feed_events),
            file_name="instalab_interazioni_demo.csv",
            mime="text/csv",
        )
