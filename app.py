"""InstaLab: Instagram-inspired research-feed prototype for Streamlit.

Customize the visual layout in styles.css, interactions in feed.js,
and example posts/stimuli in posts.json. Demo events stay in session only.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import random
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


participant_id = str(st.query_params.get("PROLIFIC_PID", "DEMO_SESSION"))

if not st.session_state.get("intro_consent_accepted", False):
    st.markdown(
        """
        <style>
          .st-key-study_intro {
            width: min(100%, 760px); margin: 48px auto; padding: 40px;
            border: 1px solid #e8e8ec; border-radius: 24px;
            color: #17171b; background: #fff;
            box-shadow: 0 16px 60px #17171b08;
          }
          .st-key-study_intro h1 {
            font-size: clamp(2rem, 5vw, 3rem); line-height: 1.12;
            letter-spacing: -0.04em; padding-top: 12px;
          }
          .st-key-study_intro h2 {font-size: 1.15rem; padding-top: 24px;}
          .st-key-study_intro p {line-height: 1.7;}
          .st-key-study_intro .intro-brand {
            color: #737373; font-size: .8rem; font-weight: 700;
            letter-spacing: .16em; text-transform: uppercase;
          }
          .st-key-study_intro .intro-brand span {color: #f24d81;}
          .st-key-study_intro .intro-subtitle {color: #737373; font-size: 1.1rem;}
          .st-key-study_intro button {min-height: 48px; border-radius: 12px;}
          .st-key-study_intro [data-testid="stCheckbox"] {margin: 20px 0 12px;}
          @media (max-width: 640px) {
            .st-key-study_intro {
              margin: 16px auto; padding: 24px 20px; width: calc(100% - 24px);
              border-radius: 18px;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="study_intro"):
        st.markdown('<div class="intro-brand">InstaLab<span> ●</span></div>', unsafe_allow_html=True)
        st.title("Faces in the Digital Age")
        st.markdown(
            '<p class="intro-subtitle">A study on face perception and recognition</p>',
            unsafe_allow_html=True,
        )
        st.write(
            "This study explores how people perceive faces in digital environments "
            "and how they recognise faces they have encountered before. "
            "We are interested in your own impressions and memory judgements."
        )
        st.subheader("What you will do")
        st.write(
            "The planned study has two phases. First, you will view photographs "
            "of faces in a simulated social media feed and judge whether each face "
            "is real or generated by artificial intelligence. Later, you will view "
            "previously presented and new faces and judge whether you have seen "
            "them before. You may also be asked how confident you are in your answers. "
            "Instructions will be provided for each task."
        )
        st.info(
            "Prototype notice: this version opens the demonstration feed only. "
            "The face discrimination and recognition tasks are not yet available."
        )
        st.subheader("Your participation")
        st.write(
            "Participation is voluntary. You may choose not to begin, or stop at any "
            "time by closing this page. Please read the study information below "
            "before deciding whether to continue."
        )
        st.warning(
            "Study information to complete before participant recruitment:\n\n"
            "- [TO COMPLETE: research team, institution and contact details]\n"
            "- [TO COMPLETE: eligibility requirements and expected duration]\n"
            "- [TO COMPLETE: foreseeable risks or discomfort, and potential benefits]\n"
            "- [TO COMPLETE: compensation and implications of stopping early]\n"
            "- [TO COMPLETE: data collected, use of Prolific identifiers, privacy, "
            "storage, retention and access arrangements]\n"
            "- [TO COMPLETE: withdrawal of submitted data and any applicable limits]\n"
            "- [TO COMPLETE: ethics review information, if applicable, and participant "
            "rights or complaints contact]"
        )
        accepted = st.checkbox(
            "I have read the information above and voluntarily agree to take part "
            "in this preliminary demonstration.",
            key="intro_consent_checkbox",
        )
        if st.button(
            "I agree — Start the experiment",
            disabled=not accepted,
            type="primary",
            width="stretch",
        ) and accepted:
            st.session_state.intro_consent_accepted = True
            st.session_state.intro_consent_accepted_at = datetime.now(timezone.utc).isoformat()
            st.session_state.intro_consent_participant_id = participant_id
            st.rerun()
    st.stop()

study = load_stimuli()
css, js = load_frontend()

posts_by_id = {post["id"]: post for post in study.get("posts", [])}
if (
    "feed_post_order" not in st.session_state
    or set(st.session_state.feed_post_order) != set(posts_by_id)
):
    st.session_state.feed_post_order = random.SystemRandom().sample(
        list(posts_by_id), k=len(posts_by_id)
    )
ordered_posts = [posts_by_id[post_id] for post_id in st.session_state.feed_post_order]

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
        "posts": ordered_posts,
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
