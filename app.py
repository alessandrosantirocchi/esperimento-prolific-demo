"""InstaLab: Instagram-inspired research-feed prototype for Streamlit.

Customize the visual layout in styles.css, interactions in feed.js,
and example posts/stimuli in posts.json. Events are also committed to local SQLite.
"""

from __future__ import annotations

import json
import math
import random
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from event_store import save_events
from recognition import make_plan, score_response
from image_assets import prepare_image
from export_data import csv_bytes as export_csv
from research_dashboard import render_dashboard

BASE = Path(__file__).resolve().parent
st.set_page_config(
    page_title="InstaLab | Social Feed Simulation",
    page_icon="📷",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if str(st.query_params.get("researcher", "0")) == "1":
    render_dashboard()
    st.stop()

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
      /* Impression events trigger reruns; keep the stimulus at full opacity. */
      .st-key-instalab_main_feed { opacity: 1 !important; transition: none !important; }
      .st-key-recognition_info {max-width:700px;margin:48px auto;padding:24px;color:#202027;}
      .st-key-recognition_info h1, .st-key-recognition_info p {color:#202027;}
    </style>
    """,
    unsafe_allow_html=True,
)


def local_image_data(filename: str, region: dict | None = None) -> str:
    """Serve local images from the repository root or its stimuli directory."""
    candidate = (BASE / str(filename)).resolve()
    if candidate.parent not in {BASE, BASE / "stimuli"} or candidate.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        return ""
    if not candidate.is_file():
        return ""
    return prepare_image(candidate, region).url


def load_stimuli() -> dict:
    raw = json.loads((BASE / "posts.json").read_text(encoding="utf-8"))
    images = {}
    def image_data(filename, region=None):
        key = (filename, json.dumps(region, sort_keys=True))
        if key not in images:
            images[key] = local_image_data(filename, region)
        return images[key]
    for post in raw.get("posts", []) + raw.get("recognition_new_posts", []):
        post["image_url"] = image_data(post.get("image", ""), post.get("image_region"))
        if not post["image_url"]:
            raise ValueError("A required stimulus image is missing")
        post["avatar_url"] = image_data(post.get("avatar", post.get("image", "")))
    for story in raw.get("stories", []):
        story["image_url"] = local_image_data(story.get("image", ""))
    return raw


def load_frontend() -> tuple[str, str]:
    return (
        (BASE / "styles.css").read_text(encoding="utf-8"),
        (BASE / "feed.js").read_text(encoding="utf-8"),
    )


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
          .st-key-study_intro {color-scheme: light;}
          .st-key-study_intro h1, .st-key-study_intro h2,
          .st-key-study_intro [data-testid="stMarkdownContainer"],
          .st-key-study_intro label, .st-key-study_intro summary {color:#202027;}
          .st-key-study_intro p {line-height: 1.75;}
          .st-key-study_intro [data-testid="stCaptionContainer"],
          .st-key-study_intro [data-testid="stCaptionContainer"] p {color:#60606d;}
          .st-key-study_intro [data-testid="stExpander"] details {
            background:#f7f8fa; border:1px solid #e4e6ec; border-radius:14px;
            margin:16px 0 8px;
          }
          .st-key-study_intro [data-testid="stExpander"] summary {font-weight:600;}
          .st-key-study_intro [data-testid="stExpander"] li {margin-bottom:8px;}
          .st-key-study_intro .intro-actions {
            display:flex; flex-wrap:wrap; gap:8px; margin:16px 0 20px;
          }
          .st-key-study_intro .intro-actions span {
            background:#f3f5f8; color:#414552; border:1px solid #e6e9ef;
            border-radius:24px; padding:7px 15px; font-size:.9rem;
          }
          .st-key-study_intro .intro-brand {
            color: #737373; font-size: .8rem; font-weight: 700;
            letter-spacing: .16em; text-transform: uppercase;
          }
          .st-key-study_intro .intro-brand span {color: #f24d81;}
          .st-key-study_intro .intro-subtitle {color: #737373; font-size: 1.1rem;}
          .st-key-study_intro button {min-height: 48px; border-radius: 12px;}
          .st-key-study_intro button[kind="primary"]:not(:disabled) {
            background:#007bc4; border-color:#007bc4; color:#fff;
          }
          .st-key-study_intro button[kind="primary"]:not(:disabled) p {color:#fff;}
          .st-key-study_intro button[kind="primary"]:disabled {
            background:#f0f2f5; border-color:#e4e6ec;
          }
          .st-key-study_intro button[kind="primary"]:disabled p {color:#666b77;}
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
            '<p class="intro-subtitle">Uno studio sulla percezione dei volti</p>',
            unsafe_allow_html=True,
        )
        st.write(
            "Immagina di aprire Instagram: davanti a te trovi un feed di post "
            "con fotografie di volti di persone. Scorri le immagini e interagisci "
            "come faresti normalmente sui social. Puoi mettere like ai post che "
            "ti piacciono, lasciare un commento oppure esprimere un dislike."
        )
        st.markdown(
            '<div class="intro-actions"><span>♡ Metti like</span>'
            '<span>Lascia un commento</span><span>Esprimi un dislike</span></div>',
            unsafe_allow_html=True,
        )
        st.subheader("La tua partecipazione")
        st.write(
            "Sei tu a scegliere se partecipare. Puoi decidere di non iniziare "
            "o fermarti in qualsiasi momento, semplicemente chiudendo la pagina. "
            "Prima di continuare, leggi le informazioni sullo studio e indica "
            "il tuo consenso."
        )
        st.caption(
            "Versione dimostrativa · Le informazioni sullo studio devono essere "
            "completate prima della raccolta dati."
        )
        with st.expander("Informazioni sullo studio — da completare"):
            st.markdown(
                "- [DA COMPLETARE: gruppo di ricerca, istituzione e contatti]\n"
                "- [DA COMPLETARE: requisiti di partecipazione e durata prevista]\n"
                "- [DA COMPLETARE: possibili rischi, disagi e benefici]\n"
                "- [DA COMPLETARE: compenso e conseguenze dell'interruzione]\n"
                "- [DA COMPLETARE: dati raccolti, identificativi Prolific, privacy, "
                "conservazione e accesso ai dati]\n"
                "- [DA COMPLETARE: ritiro dei dati e relativi limiti]\n"
                "- [DA COMPLETARE: eventuale revisione etica e contatti per diritti e reclami]"
            )
        accepted = st.checkbox(
            "Ho letto le informazioni sopra riportate e acconsento volontariamente "
            "a partecipare a questa dimostrazione preliminare.",
            key="intro_consent_checkbox",
        )
        if st.button(
            "Acconsento — Inizia l'esperimento",
            disabled=not accepted,
            type="primary",
            width="stretch",
        ) and accepted:
            st.session_state.intro_consent_accepted = True
            st.session_state.intro_consent_accepted_at = datetime.now(timezone.utc).isoformat()
            st.session_state.intro_consent_participant_id = participant_id
            st.rerun()
    st.stop()

try:
    study = load_stimuli()
except (OSError, ValueError, KeyError):
    st.error("Non è stato possibile caricare le fotografie. Ricarica la pagina; se il problema persiste, contatta il ricercatore.")
    st.stop()
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
all_posts_by_id = {p["id"]: p for p in study.get("posts", []) + study.get("recognition_new_posts", [])}
if "recognition_plan" not in st.session_state:
    st.session_state.recognition_plan = make_plan(study["posts"], study.get("recognition_new_posts", []))
if "experiment_phase" not in st.session_state:
    st.session_state.experiment_phase = "feed"

if "feed_events" not in st.session_state:
    st.session_state.feed_events = []
    st.session_state.seen_event_ids = set()
if "recording_session_id" not in st.session_state:
    st.session_state.recording_session_id = str(uuid.uuid4())

phase = st.session_state.experiment_phase
if phase == "recognition_intro":
    with st.container(key="recognition_info"):
        st.title("Hai già visto questo volto?")
        st.write("Ora vedrai alcuni volti del feed precedente insieme a volti nuovi. Per ogni fotografia, indica se ricordi di averla vista nella prima parte.")
        st.markdown("**OLD — Già visto:** il volto era presente nel feed precedente.\n\n**NEW — Nuovo:** il volto non era presente nel feed precedente.")
        st.write("Scegli una sola risposta per ogni volto. Dopo la scelta passerai alla fotografia successiva. Non verrà mostrato se la risposta è corretta.")
        if st.button("Inizia il riconoscimento", type="primary"):
            event = {"event_id": "recognition_started", "event_type": "recognition_started",
                     "participant_id": participant_id, "session_id": st.session_state.recording_session_id,
                     "phase": "recognition", "server_received_ts": datetime.now(timezone.utc).isoformat()}
            try:
                save_events(st.session_state.recording_session_id, [event])
            except (sqlite3.Error, OSError):
                st.error("Impossibile salvare l'avvio. Riprova senza chiudere la pagina.")
            else:
                st.session_state.feed_events.append(event)
                st.session_state.seen_event_ids.add(event["event_id"])
                st.session_state.experiment_phase = "recognition"
                st.rerun()
    st.stop()

answered_ids = {e["post_id"] for e in st.session_state.feed_events if e.get("event_type") == "recognition_response"}
remaining_trials = [t for t in st.session_state.recognition_plan if t["post_id"] not in answered_ids]
if phase == "recognition" and not remaining_trials:
    with st.container(key="recognition_info"):
        st.title("Prova completata")
        st.write("Grazie per la partecipazione. Tutte le risposte sono state salvate sul server.")
        if str(st.query_params.get("preview", "0")) == "1":
            st.download_button("Scarica interazioni CSV", export_csv(st.session_state.feed_events),
                               "instalab_interazioni.csv", "text/csv")
    st.stop()

seen_posts = {e.get("post_id") for e in st.session_state.feed_events if e.get("event_type") == "post_impression" and e.get("phase", "feed") == "feed"}
missing_post_ids = [post_id for post_id in st.session_state.feed_post_order if post_id not in seen_posts]
phase1_ready = not missing_post_ids
visible_posts = ordered_posts if phase == "feed" else [all_posts_by_id[remaining_trials[0]["post_id"]]]
# Recognition receives only display data, never the answer key or old/new labels.
if phase == "recognition":
    visible_posts = [{k: p[k] for k in ("id", "image_url", "image_region", "image_position") if k in p} for p in visible_posts]
    visible_posts[0]["id"] = remaining_trials[0]["trial_id"]

# Send shared source sheets once, rather than once per tile on every event.
image_sources = {}
image_keys = {}
component_posts = []
for post in visible_posts:
    image_url = post.get("image_url", "")
    if image_url not in image_keys:
        image_keys[image_url] = f"asset-{len(image_keys)}"
        image_sources[image_keys[image_url]] = image_url
    component_posts.append({**{k: v for k, v in post.items() if k != "image_url"},
                            "image_key": image_keys[image_url]})
    # Cropping has already been applied to the cached display asset.
    component_posts[-1].pop("image_region", None)

preload_images = []
if phase == "recognition":
    preload_images = [all_posts_by_id[t["post_id"]]["image_url"] for t in remaining_trials[1:3]]

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
        "posts": component_posts,
        "image_sources": image_sources,
        "preload_images": preload_images,
        "stories": study.get("stories", []) if phase == "feed" else [],
        "phase": phase,
        "phase1_ready": phase1_ready,
        "missing_post_ids": missing_post_ids,
        "trial_number": len(answered_ids) + 1,
        "trial_total": len(st.session_state.recognition_plan),
        "title": study.get("display_name", "InstaLab"),
        "participant_id": participant_id,
        "history": [{k: v for k, v in e.items() if k != "details"} if e.get("event_type") in {"session_started", "recognition_plan_assigned"} else
                    {**e, "details": {k: v for k, v in e.get("details", {}).items() if k not in {"target", "correct"}}}
                    for e in st.session_state.feed_events],
    },
    default={"events": []},
    on_events_change=lambda: None,
    width="stretch",
)

# Acknowledge events in session state only after the database transaction commits.
new_events = response.events or []
pending_events = []
pending_ids = set()
batch_answered_ids = set(answered_ids)
batch_seen_posts = set(seen_posts)
transition_requested = False
for event in new_events:
    if not isinstance(event, dict):
        continue
    event_id = str(event.get("event_id", ""))
    if not event_id or event_id in st.session_state.seen_event_ids or event_id in pending_ids:
        continue
    pending_ids.add(event_id)
    event = dict(event)
    event["phase"] = phase
    if phase == "feed" and event.get("event_type") == "post_impression":
        if event.get("post_id") not in posts_by_id or event["post_id"] in batch_seen_posts:
            continue
        batch_seen_posts.add(event["post_id"])
    if event.get("event_type") == "begin_recognition":
        if phase != "feed" or not phase1_ready:
            continue
        transition_requested = True
    if phase == "recognition":
        if event.get("event_type") != "recognition_response":
            continue
        trial = remaining_trials[0]
        if event.get("post_id") != trial["trial_id"] or trial["post_id"] in batch_answered_ids:
            continue
        if not isinstance(event.get("details"), dict):
            continue
        rt = event["details"].get("response_time_ms")
        if type(rt) not in {float, int} or not math.isfinite(rt) or rt < 0:
            continue
        event["trial_id"] = trial["trial_id"]
        event["post_id"] = trial["post_id"]
        try:
            score = score_response(st.session_state.recognition_plan, event["post_id"], event.get("details", {}).get("response"))
        except ValueError:
            continue
        event["details"] = {**event.get("details", {}), **score}
        batch_answered_ids.add(event["post_id"])
    elif event.get("event_type") == "recognition_response":
        continue
    event["session_id"] = st.session_state.recording_session_id
    event["participant_id"] = participant_id
    post = all_posts_by_id.get(event.get("post_id"))
    event["stimulus_id"] = post.get("stimulus_id", "") if post else ""
    event["stimulus_type"] = post.get("stimulus_type", "") if post else ""
    event["server_received_ts"] = datetime.now(timezone.utc).isoformat()
    pending_events.append(event)

try:
    if not st.session_state.get("recognition_plan_recorded", False):
        pending_events.append({"event_id": "recognition_plan_assigned", "event_type": "recognition_plan_assigned",
                               "session_id": st.session_state.recording_session_id,
                               "participant_id": participant_id,
                               "server_received_ts": datetime.now(timezone.utc).isoformat(),
                               "details": {"recognition_plan": st.session_state.recognition_plan}})
    if phase == "recognition" and len(batch_answered_ids) == len(st.session_state.recognition_plan):
        pending_events.append({"event_id": "recognition_completed", "event_type": "recognition_completed",
                               "session_id": st.session_state.recording_session_id,
                               "participant_id": participant_id, "phase": "recognition",
                               "server_received_ts": datetime.now(timezone.utc).isoformat()})
    # Include consent and presentation order once, in the same durable batch.
    if not st.session_state.get("recording_initialized", False):
        pending_events.insert(0, {
            "event_id": "session_started", "event_type": "session_started",
            "session_id": st.session_state.recording_session_id,
            "participant_id": participant_id,
            "server_received_ts": datetime.now(timezone.utc).isoformat(),
            "details": {"consent_accepted_at": st.session_state.intro_consent_accepted_at,
                        "post_order": st.session_state.feed_post_order,
                        "recognition_plan": st.session_state.recognition_plan},
        })
    if pending_events:
        save_events(st.session_state.recording_session_id, pending_events)
        st.session_state.feed_events.extend(pending_events)
        st.session_state.seen_event_ids.update(e["event_id"] for e in pending_events)
        st.session_state.recording_initialized = True
        st.session_state.recognition_plan_recorded = True
        if transition_requested:
            st.session_state.experiment_phase = "recognition_intro"
            st.rerun()
        st.rerun()
except (sqlite3.Error, OSError):
    st.error("Non è stato possibile salvare le interazioni. Lascia aperta questa pagina e riprova.")
    if st.button("Riprova il salvataggio"):
        st.rerun()

# Open ?preview=1 to inspect the research log without displaying it to participants.
if str(st.query_params.get("preview", "0")) == "1":
    with st.expander("🔬 Pannello ricercatore — anteprima e log", expanded=True):
        st.caption("Gli eventi sono salvati nel database locale del server. Per conservarli dopo la ricreazione del server serve un disco persistente o un database esterno.")
        st.write(f"Partecipante: {participant_id} · Eventi: {len(st.session_state.feed_events)}")
        st.dataframe(st.session_state.feed_events, use_container_width=True, hide_index=True)
        st.download_button(
            "Scarica interazioni CSV",
            data=export_csv(st.session_state.feed_events),
            file_name="instalab_interazioni_demo.csv",
            mime="text/csv",
        )
