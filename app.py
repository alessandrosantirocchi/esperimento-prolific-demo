"""Social Feed: Instagram-inspired research-feed prototype for Streamlit.

Customize the visual layout in styles.css, interactions in feed.js,
and the stimulus catalog in stimuli.csv and images/. Events are stored in SQLite.
"""

from __future__ import annotations

import math
import random
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from event_store import save_events, SessionDeletedError, is_session_deleted
from recognition import make_plan, score_response
import image_assets
from export_data import csv_bytes as export_csv
from research_dashboard import render_dashboard
from experiment_protocol import PROTOCOL_VERSION
from participant_data import GENDER_OPTIONS, EDUCATION_OPTIONS, validate_demographics
from feed_metrics import TRACKING_VERSION, FEED_METRIC_COLUMNS, feed_metrics_rows, valid_view_details
from stimulus_catalog import (load_catalog, select_sets, CatalogError, METADATA_FIELDS,
                              display_post, public_history)

BASE = Path(__file__).resolve().parent
FEED_INTERFACE_VERSION = "clean-feed-v2"
st.set_page_config(
    page_title="Social Feed | Faces in the Digital Age",
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
      [data-testid="stSpinner"] {position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);
        z-index:10000;width:max-content;max-width:calc(100vw - 32px);padding:16px 20px;
        border:1px solid #e4e6ec;border-radius:14px;background:#fff;color:#202027;
        box-shadow:0 8px 32px #20202718;}
      [data-testid="stSpinner"] p {color:#202027;}
    </style>
    """,
    unsafe_allow_html=True,
)


def load_stimuli(catalog, selection, include_new_images=False) -> dict:
    by_id = {record["id"]: record for record in catalog.records}
    # Reserve every stimulus up front, but defer encoding the unseen memory
    # faces until needed (or warm them in the background). Assignments stay
    # identical; all memory assets are ready before its first trial is shown.
    image_ids = selection["feed"] + (selection["new"] if include_new_images else [])
    image_paths = [catalog.base / by_id[i]["image"] for i in image_ids]
    # Streamlit can retain the older imported module during a live update.
    # Its original single-image API remains compatible with the new app.
    batch_loader = getattr(image_assets, "prepare_images", None)
    images = (batch_loader(image_paths) if batch_loader is not None
              else [image_assets.prepare_image(path) for path in image_paths])
    assets = dict(zip(image_ids, images))
    study = {"posts": [], "recognition_new_posts": [], "stories": [], "display_name": "Social Feed"}
    for key, destination in (("feed", "posts"), ("new", "recognition_new_posts")):
        for index, identifier in enumerate(selection[key], 1):
            record = by_id[identifier]
            study[destination].append({**record, "image_url": assets[identifier].url if identifier in assets else "",
                                       "avatar_url": "", "username": f"profilo.{index:02}", "caption": "",
                                       "comments": [], "location": "", "initial_likes": 0,
                                       "minutes_ago": 30, "verified": False})
    return study


def load_frontend() -> tuple[str, str]:
    return (
        (BASE / "styles.css").read_text(encoding="utf-8"),
        (BASE / "feed_tracking.js").read_text(encoding="utf-8") + "\n" + (BASE / "feed.js").read_text(encoding="utf-8"),
    )


if "participant_id" not in st.session_state:
    # Preserve an already-consented session across a deployment; new visits get
    # an internal code that does not depend on recruitment URL parameters.
    previous_id = (st.session_state.get("intro_consent_participant_id")
                   if st.session_state.get("intro_consent_accepted", False) else None)
    st.session_state.participant_id = previous_id or f"P_{uuid.uuid4().hex}"
participant_id = st.session_state.participant_id

if not st.session_state.get("intro_consent_accepted", False):
    st.markdown(
        """
        <style>
          .st-key-study_intro {
            width: min(100% - 32px, 720px); margin: 36px auto; padding: 36px;
            border: 1px solid #e9e9f0; border-radius: 24px;
            color: #17171b; background: #fff;
            box-shadow: 0 18px 64px #28203909;
          }
          .st-key-study_intro h1 {
            font-size: clamp(2rem, 5.2vw, 2.9rem); line-height: 1.1;
            letter-spacing: -0.045em; padding: 0 0 12px;
          }
          .st-key-study_intro {color-scheme: light;}
          .st-key-study_intro h1,
          .st-key-study_intro [data-testid="stMarkdownContainer"],
          .st-key-study_intro label, .st-key-study_intro summary {color:#202027;}
          .st-key-study_intro p {line-height: 1.65;}
          .st-key-study_intro [data-testid="stCaptionContainer"],
          .st-key-study_intro [data-testid="stCaptionContainer"] p {color:#60606d;}
          .st-key-study_intro [data-testid="stExpander"] details {
            background:#f7f8fa; border:1px solid #e4e6ec; border-radius:14px;
            margin:12px 0 8px;
          }
          .st-key-study_intro [data-testid="stExpander"] summary {font-weight:600;}
          .st-key-study_intro [data-testid="stExpander"] li {margin-bottom:8px;}
          .st-key-study_intro .intro-actions {
            display:grid; grid-template-columns:repeat(3, minmax(0, 1fr));
            gap:10px; margin:6px 0 20px;
          }
          .st-key-study_intro .intro-action {
            display:flex; align-items:center; justify-content:center; gap:9px;
            padding:16px 8px; border:1px solid #ececf2; border-radius:14px;
            background:#fcfcfe; font-size:.9rem; font-weight:600;
          }
          .st-key-study_intro .intro-icon {
            display:inline-flex; flex-shrink:0; align-items:center; justify-content:center;
            width:38px; height:38px; border-radius:12px;
          }
          .st-key-study_intro .intro-like {background:#fff0f5;color:#ce2861;}
          .st-key-study_intro .intro-comment {background:#edf5ff;color:#2866b1;}
          .st-key-study_intro .intro-dislike {background:#f4efff;color:#7654b5;}
          .st-key-study_intro .intro-next {
            display:flex; align-items:flex-start; gap:12px; margin:0 0 18px;
            padding:16px; background:#f8f8fc; border-radius:14px;
          }
          .st-key-study_intro .intro-next svg {flex-shrink:0;color:#77718e;margin-top:3px;}
          .st-key-study_intro .intro-next p {margin:0;font-size:.94rem;color:#525261;}
          .st-key-study_intro .intro-topline {
            display:flex; align-items:center; justify-content:space-between;
            gap:12px; margin-bottom:24px;
          }
          .st-key-study_intro .intro-brand {
            color:#34313c; font-size:1rem; font-weight:750; letter-spacing:-.03em;
          }
          .st-key-study_intro .intro-brand span {color:#f24d81;}
          .st-key-study_intro .intro-demo {
            color:#6c6579; background:#f4f2f8; padding:5px 10px;
            border-radius:20px; font-size:.72rem;
          }
          .st-key-study_intro .intro-subtitle {color:#666272;font-size:1.06rem;margin-bottom:18px;}
          .st-key-study_intro button {min-height: 48px; border-radius: 12px;}
          .st-key-study_intro button[kind="primary"]:not(:disabled) {
            background:#007bc4; border-color:#007bc4; color:#fff;
          }
          .st-key-study_intro button[kind="primary"]:not(:disabled) p {color:#fff;}
          .st-key-study_intro button[kind="primary"]:disabled {
            background:#f0f2f5; border-color:#e4e6ec;
          }
          .st-key-study_intro button[kind="primary"]:disabled p {color:#666b77;}
          .st-key-study_intro [data-testid="stCheckbox"] {margin: 12px 0 14px;}
          @media (max-width: 640px) {
            .st-key-study_intro {
              margin: 12px auto; padding: 24px 18px; width: calc(100% - 24px);
              border-radius: 18px;
            }
            .st-key-study_intro .intro-action {flex-direction:column;gap:7px;padding:12px 4px;font-size:.82rem;}
            .st-key-study_intro .intro-topline {margin-bottom:20px;}
            .st-key-study_intro .intro-actions {gap:8px;}
          }
        </style>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="study_intro"):
        st.markdown(
            '<div class="intro-topline"><div class="intro-brand">Social Feed<span> ●</span></div>'
            '<span class="intro-demo">Versione dimostrativa</span></div>', unsafe_allow_html=True,
        )
        st.title("Faces in the Digital Age")
        st.markdown(
            '<p class="intro-subtitle">Scorri il feed, proprio come sui social.</p>',
            unsafe_allow_html=True,
        )
        st.write(
            "Immagina di aprire il tuo social preferito. Troverai un feed di post "
            "con fotografie di volti: guardali al tuo ritmo e scorri fino alla fine."
        )
        st.write(
            "Se ti va, interagisci come faresti di solito: metti Like, lascia un "
            "commento o esprimi un Dislike. Puoi anche passare al post successivo "
            "senza reagire."
        )
        st.markdown(
            '<div class="intro-actions" role="list" aria-label="Interazioni disponibili nel feed">'
            '<div class="intro-action" role="listitem"><span class="intro-icon intro-like">'
            '<svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<path d="M20.8 4.6a5.4 5.4 0 0 0-7.7 0L12 5.7l-1.1-1.1a5.4 5.4 0 0 0-7.7 7.7L12 21l8.8-8.7a5.4 5.4 0 0 0 0-7.7z"/></svg>'
            '</span><span>Like</span></div>'
            '<div class="intro-action" role="listitem"><span class="intro-icon intro-comment">'
            '<svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<path d="M21 11.5a8.5 8.5 0 0 1-8.5 8.5 9.4 9.4 0 0 1-4-.9L3 21l1.9-5.5A8.5 8.5 0 1 1 21 11.5z"/>'
            '<path d="M8 10h8M8 14h5"/></svg></span><span>Commenta</span></div>'
            '<div class="intro-action" role="listitem"><span class="intro-icon intro-dislike">'
            '<svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<path d="M17 3h4v11h-4zM17 13l-5 8h-1a2 2 0 0 1-2-2l1-5H5a2 2 0 0 1-2-2l1-7a2 2 0 0 1 2-2h11z"/>'
            '</svg></span><span>Dislike</span></div></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="intro-next"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            '<path d="M4 12h16m-6-6 6 6-6 6"/></svg>'
            '<p>Alla fine del feed, premi <strong>Continua</strong>. Seguirà una '
            '<strong>seconda fase</strong>: riceverai le istruzioni prima di iniziarla.</p></div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "La partecipazione è volontaria. Puoi interrompere in qualsiasi "
            "momento chiudendo la pagina."
        )
        with st.expander("Consenso informato", expanded=False):
            st.caption("Versione dimostrativa: le informazioni seguenti devono essere completate prima della raccolta dati.")
            st.markdown(
                "- [DA COMPLETARE: gruppo di ricerca, istituzione e contatti]\n"
                "- [DA COMPLETARE: requisiti, durata, rischi/disagi e benefici, "
                "compenso e conseguenze dell'interruzione]\n"
                "- [DA COMPLETARE: dati raccolti (genere, età, istruzione e risposte), codici di partecipazione e sessione, privacy, "
                "conservazione, accesso e ritiro dei dati con relativi limiti]\n"
                "- [DA COMPLETARE: eventuale revisione etica e contatti per diritti e reclami]"
            )
        accepted = st.checkbox(
            "Ho letto le informazioni sullo studio e acconsento a partecipare "
            "a questa dimostrazione.",
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

if "recording_session_id" not in st.session_state:
    st.session_state.recording_session_id = str(uuid.uuid4())
if "feed_events" not in st.session_state:
    st.session_state.feed_events = []
    st.session_state.seen_event_ids = set()

try:
    deleted = is_session_deleted(st.session_state.recording_session_id)
except (sqlite3.Error, OSError):
    st.error("Il database non è disponibile. Riprova senza chiudere la pagina.")
    st.stop()
if st.session_state.get("recording_deleted", False) or deleted:
    st.session_state.feed_events = []
    st.session_state.seen_event_ids = set()
    st.session_state.recording_deleted = True
    st.info("Questa sessione è stata eliminata dal ricercatore. Per iniziare una nuova prova, ricarica la pagina.")
    st.stop()

# Existing runs keep their place; newly consented sessions complete this step
# before selecting or loading faces. Mark completion only after a durable save.
if not st.session_state.get("demographics_completed", False) and not st.session_state.get("recording_initialized", False):
    st.markdown("""
        <style>
          .st-key-participant_details {width:min(100% - 24px,600px);margin:32px auto;padding:32px;
            border:1px solid #e9e9f0;border-radius:24px;background:#fff;color:#202027;
            box-shadow:0 18px 64px #28203909;color-scheme:light;}
          .st-key-participant_details h1 {font-size:clamp(1.8rem,5vw,2.4rem);letter-spacing:-.04em;padding-top:0;}
          .st-key-participant_details h1,.st-key-participant_details p,.st-key-participant_details label {color:#202027;}
          .st-key-participant_details [data-baseweb="select"]>div,
          .st-key-participant_details [data-baseweb="input"],
          .st-key-participant_details [data-testid="stSelectbox"] [role="group"],
          .st-key-participant_details [data-testid="stNumberInputContainer"] {background:#f8f9fc;color:#202027;border-color:#dddfea;}
          .st-key-participant_details input {color:#202027;background:transparent;}
          .st-key-participant_details input::placeholder {color:#747481;opacity:1;}
          .st-key-participant_details [data-testid="stSelectbox"] button {background:transparent;color:#60606d;}
          .st-key-participant_details [data-testid="stNumberInputContainer"] button {background:transparent;}
          .st-key-participant_details [data-testid="stNumberInputContainer"] svg {color:#8b8d99;}
          .st-key-participant_details [data-testid="stSelectbox"] [role="group"]:focus-within,
          .st-key-participant_details [data-testid="stNumberInputContainer"]:focus-within {border-color:#007bc4;box-shadow:0 0 0 1px #007bc4;}
          .st-key-participant_details [data-testid="stForm"] {padding:0;}
          .st-key-participant_details [data-testid="stVerticalBlock"] {gap:12px !important;}
          .st-key-participant_details button[kind^="primary"] {background:#007bc4;border-color:#007bc4;border-radius:12px;min-height:48px;}
          .st-key-participant_details button[kind^="primary"] p {color:#fff;}
          .st-key-participant_details [data-testid="stCaptionContainer"] p {color:#60606d;}
          @media(max-width:640px){.st-key-participant_details {margin:12px auto;padding:24px 18px;border-radius:18px;}}
        </style>
    """, unsafe_allow_html=True)
    with st.container(key="participant_details"):
        st.title("Prima di iniziare")
        st.write("Indica queste informazioni: saranno associate al tuo codice partecipante.")
        with st.form("participant_details_form", border=False):
            gender = st.selectbox("Genere", list(GENDER_OPTIONS), index=None, format_func=GENDER_OPTIONS.get,
                                  placeholder="Seleziona una risposta", key="demographic_gender")
            age = st.number_input("Età (anni compiuti)", min_value=0, value=None, step=1,
                                  placeholder="Inserisci la tua età", key="demographic_age")
            education = st.selectbox("Titolo di studio più alto conseguito", list(EDUCATION_OPTIONS), index=None,
                                     format_func=EDUCATION_OPTIONS.get, placeholder="Seleziona una risposta",
                                     help="Indica un titolo già completato, anche se stai ancora studiando.",
                                     key="demographic_education")
            submitted = st.form_submit_button("Continua", type="primary", width="stretch")
        if submitted:
            try:
                values = validate_demographics(gender, age, education)
            except ValueError as exc:
                st.error(str(exc))
            else:
                event = {"event_id": "demographics_submitted", "event_type": "demographics_submitted",
                         "phase": "demographics", "participant_id": participant_id,
                         "session_id": st.session_state.recording_session_id, **values,
                         "server_received_ts": datetime.now(timezone.utc).isoformat(),
                         "details": {**values, "consent_accepted_at": st.session_state.intro_consent_accepted_at}}
                try:
                    save_events(st.session_state.recording_session_id, [event])
                except SessionDeletedError:
                    st.session_state.recording_deleted = True
                    st.rerun()
                except (sqlite3.Error, OSError):
                    st.error("Non è stato possibile salvare le risposte. Riprova con Continua senza chiudere la pagina.")
                else:
                    st.session_state.participant_demographics = values
                    st.session_state.demographics_completed = True
                    st.session_state.feed_events.append(event)
                    st.session_state.seen_event_ids.add(event["event_id"])
                    st.rerun()
    st.stop()

# Explain the feed again after the questionnaire, before loading any faces or
# starting behavioral tracking. Already-running sessions keep their current place.
if not st.session_state.get("feed_instructions_completed", False) and not st.session_state.get("recording_initialized", False):
    st.markdown("""
        <style>
          .st-key-feed_instructions {width:min(100% - 24px,660px);margin:32px auto;padding:32px;
            border:1px solid #e9e9f0;border-radius:24px;background:#fff;color:#202027;
            box-shadow:0 18px 64px #28203909;color-scheme:light;}
          .st-key-feed_instructions h1 {font-size:clamp(1.8rem,5vw,2.4rem);letter-spacing:-.04em;
            line-height:1.15;padding:0 0 16px;}
          .st-key-feed_instructions h1,.st-key-feed_instructions p {color:#202027;}
          .st-key-feed_instructions p {line-height:1.65;}
          .st-key-feed_instructions .feed-guide-brand {font-weight:750;color:#34313c;margin-bottom:20px;}
          .st-key-feed_instructions .feed-guide-brand span {color:#f24d81;}
          .st-key-feed_instructions .feed-guide {display:grid;gap:12px;margin:22px 0;}
          .st-key-feed_instructions .feed-guide-step {display:flex;align-items:flex-start;gap:14px;
            padding:18px;border:1px solid #ececf2;border-radius:16px;background:#fcfcfe;}
          .st-key-feed_instructions .feed-guide-icon {display:flex;align-items:center;justify-content:center;
            flex-shrink:0;width:40px;height:40px;border-radius:12px;background:#edf5ff;color:#2866b1;}
          .st-key-feed_instructions .feed-guide-social {background:#fff0f5;color:#ce2861;}
          .st-key-feed_instructions .feed-guide-step h2 {font-size:1rem;line-height:1.4;padding:0;margin:0 0 5px;color:#202027;}
          .st-key-feed_instructions .feed-guide-step p {font-size:.94rem;color:#525261;margin:0;}
          .st-key-feed_instructions button[kind="primary"] {background:#007bc4;border-color:#007bc4;
            border-radius:12px;min-height:48px;}
          .st-key-feed_instructions button[kind="primary"] p {color:#fff;}
          @media(max-width:640px){
            .st-key-feed_instructions {margin:12px auto;padding:24px 18px;border-radius:18px;}
            .st-key-feed_instructions .feed-guide-step {padding:14px;gap:12px;}
          }
        </style>
    """, unsafe_allow_html=True)
    with st.container(key="feed_instructions"):
        st.markdown('<div class="feed-guide-brand">Social Feed<span> ●</span></div>', unsafe_allow_html=True)
        st.title("Prima di aprire il feed")
        st.write("Immagina di aprire Instagram: troverai un feed di post con fotografie di volti di persone.")
        st.markdown("""
            <div class="feed-guide" role="list" aria-label="Come usare il feed">
              <div class="feed-guide-step" role="listitem">
                <span class="feed-guide-icon"><svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 3v18m-5-5 5 5 5-5M17 3h4M17 8h4M17 13h4"/></svg></span>
                <div><h2>Scorri al tuo ritmo</h2><p>Guarda i post e scorri fino alla fine del feed, come faresti normalmente su un social.</p></div>
              </div>
              <div class="feed-guide-step" role="listitem">
                <span class="feed-guide-icon feed-guide-social"><svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.8 4.6a5.4 5.4 0 0 0-7.7 0L12 5.7l-1.1-1.1a5.4 5.4 0 0 0-7.7 7.7L12 21l8.8-8.7a5.4 5.4 0 0 0 0-7.7z"/></svg></span>
                <div><h2>Interagisci liberamente</h2><p>Puoi mettere Like o Dislike, lasciare un commento o salvare un post. Puoi anche passare oltre senza reagire.</p></div>
              </div>
              <div class="feed-guide-step" role="listitem">
                <span class="feed-guide-icon"><svg width="23" height="23" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12h16m-6-6 6 6-6 6"/></svg></span>
                <div><h2>Quando hai finito</h2><p>In fondo al feed premi <strong>Continua</strong>. Seguirà una seconda fase: riceverai nuove istruzioni prima di iniziarla.</p></div>
              </div>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Ho capito — Apri il feed", key="start_feed_button", type="primary", width="stretch"):
            st.session_state.feed_instructions_completed = True
            st.rerun()
    st.stop()

participant_details = st.session_state.get("participant_demographics", {})

try:
    with st.spinner("Aggiornamento del feed…"):
        catalog = load_catalog(BASE)
        if "stimulus_selection" not in st.session_state:
            if st.session_state.get("recording_initialized", False):
                st.error("Gli stimoli sono cambiati. Ricarica la pagina per iniziare una nuova sessione.")
                st.stop()
            st.session_state.stimulus_selection = select_sets(catalog)
        if (st.session_state.stimulus_selection.get("protocol_version") != PROTOCOL_VERSION
                or st.session_state.stimulus_selection["fingerprint"] != catalog.fingerprint):
            st.error("La configurazione dello studio è cambiata. Ricarica la pagina per iniziare una nuova sessione.")
            st.stop()
        study = load_stimuli(catalog, st.session_state.stimulus_selection,
                             include_new_images=st.session_state.get("experiment_phase", "feed") == "recognition")
except (CatalogError, OSError, ValueError, KeyError):
    st.error("Non è stato possibile preparare le fotografie. Il ricercatore deve verificare la configurazione degli stimoli.")
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

phase = st.session_state.experiment_phase
if phase == "recognition_intro":
    with st.container(key="recognition_info"):
        st.title("Hai già visto questo volto?")
        st.write("Ora vedrai alcuni volti del feed precedente insieme a volti nuovi. Per ogni fotografia, indica se ricordi di averla vista nella prima parte.")
        st.markdown("**OLD — Già visto:** il volto era presente nel feed precedente.\n\n**NEW — Nuovo:** il volto non era presente nel feed precedente.")
        st.write("Scegli una sola risposta per ogni volto. Dopo la scelta passerai alla fotografia successiva. Non verrà mostrato se la risposta è corretta.")
        # Show the instructions before any outstanding image preparation, so a
        # cold server never leaves the participant waiting at the end of the feed.
        try:
            with st.spinner("Aggiornamento del feed…"):
                load_stimuli(catalog, st.session_state.stimulus_selection, include_new_images=True)
        except (OSError, ValueError, KeyError):
            st.error("Non è stato possibile aggiornare il feed. Riprova senza chiudere la pagina.")
            if st.button("Riprova aggiornamento"):
                st.rerun()
            st.stop()
        if st.button("Inizia il riconoscimento", type="primary"):
            event = {"event_id": "recognition_started", "event_type": "recognition_started",
                     "participant_id": participant_id, "session_id": st.session_state.recording_session_id,
                     **participant_details,
                     "phase": "recognition", "server_received_ts": datetime.now(timezone.utc).isoformat()}
            try:
                save_events(st.session_state.recording_session_id, [event])
            except SessionDeletedError:
                st.session_state.recording_deleted = True
                st.rerun()
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
            st.download_button("Metriche del feed (CSV)", export_csv(feed_metrics_rows(st.session_state.feed_events), FEED_METRIC_COLUMNS),
                               "feed_metrics.csv", "text/csv")
    st.stop()

seen_posts = {e.get("post_id") for e in st.session_state.feed_events if e.get("event_type") == "post_impression" and e.get("phase", "feed") == "feed"}
missing_post_ids = [post_id for post_id in st.session_state.feed_post_order if post_id not in seen_posts]
phase1_ready = not missing_post_ids
visible_posts = ordered_posts if phase == "feed" else [all_posts_by_id[remaining_trials[0]["post_id"]]]
# Recognition receives only display data, never the answer key or old/new labels.
if phase == "recognition":
    visible_posts = [{k: p[k] for k in ("id", "image_url", "image_region", "image_position") if k in p} for p in visible_posts]
    visible_posts[0]["id"] = remaining_trials[0]["trial_id"]

# Send each display asset once in the component payload.
image_sources = {}
image_keys = {}
component_posts = []
for post in visible_posts:
    image_url = post.get("image_url", "")
    if image_url not in image_keys:
        image_keys[image_url] = f"asset-{len(image_keys)}"
        image_sources[image_keys[image_url]] = image_url
    component_posts.append({**{k: v for k, v in display_post(post).items() if k != "image_url"},
                            "image_key": image_keys[image_url]})
    # Cropping has already been applied to the cached display asset.
    component_posts[-1].pop("image_region", None)

preload_images = []
if phase == "recognition":
    preload_images = [all_posts_by_id[t["post_id"]]["image_url"] for t in remaining_trials[1:3]]

# The feed tracker acknowledges the browser's per-session asset cache. Timer
# checkpoints must not retransmit every face on each Streamlit rerun.
if phase == "feed" and any(e.get("event_type") == "feed_tracking_started" for e in st.session_state.feed_events):
    image_sources = {}

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
        "title": study.get("display_name", "Social Feed"),
        "participant_id": participant_id,
        "session_id": st.session_state.recording_session_id,
        "history": public_history(st.session_state.feed_events),
    },
    default={"events": []},
    on_events_change=lambda: None,
    width="stretch",
)

# Speculative server-side preparation does not expose NEW faces to the browser
# and does not touch session state, events, or clocks in the background thread.
if phase == "feed":
    prefetch = getattr(image_assets, "prefetch_images", None)
    if prefetch is not None:
        try:
            prefetch([catalog.base / post["image"] for post in study["recognition_new_posts"]])
        except (OSError, ValueError):
            pass  # Foreground validation/preparation will report any asset issue.

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
    if str(event.get("event_type", "")).startswith("feed_"):
        if phase != "feed":
            continue
        details = event.get("details", {})
        if event.get("event_type") == "feed_view":
            if event.get("post_id") not in posts_by_id or not valid_view_details(details):
                continue
        elif event.get("event_type") in {"feed_tracking_started", "feed_tracking_finalized"}:
            if not isinstance(details, dict) or details.get("tracking_version") != TRACKING_VERSION:
                continue
        else:
            continue
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
    for field in METADATA_FIELDS:
        event[field] = post.get(field, "") if post else ""
    event["feed_position"] = st.session_state.feed_post_order.index(event["post_id"]) + 1 if event.get("post_id") in posts_by_id else ""
    event["server_received_ts"] = datetime.now(timezone.utc).isoformat()
    pending_events.append(event)

try:
    if not st.session_state.get("recognition_plan_recorded", False):
        pending_events.append({"event_id": "recognition_plan_assigned", "event_type": "recognition_plan_assigned",
                               "session_id": st.session_state.recording_session_id,
                               "participant_id": participant_id,
                               "server_received_ts": datetime.now(timezone.utc).isoformat(),
                               "details": {"recognition_plan": st.session_state.recognition_plan,
                                           "catalog_fingerprint": catalog.fingerprint,
                                           "protocol_version": PROTOCOL_VERSION}})
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
                        "recognition_plan": st.session_state.recognition_plan,
                        "catalog_fingerprint": catalog.fingerprint,
                        "protocol_version": PROTOCOL_VERSION,
                        "feed_tracking_version": TRACKING_VERSION,
                        "feed_interface_version": FEED_INTERFACE_VERSION,
                        "stimuli": [{field: p[field] for field in ("id", "image", "sha256") + METADATA_FIELDS}
                                    for p in study["posts"] + study["recognition_new_posts"]]},
        })
    if pending_events:
        for event in pending_events:
            event.update(participant_details)
        save_events(st.session_state.recording_session_id, pending_events)
        st.session_state.feed_events.extend(pending_events)
        st.session_state.seen_event_ids.update(e["event_id"] for e in pending_events)
        st.session_state.recording_initialized = True
        st.session_state.recognition_plan_recorded = True
        if transition_requested:
            st.session_state.experiment_phase = "recognition_intro"
            st.rerun()
        st.rerun()
except SessionDeletedError:
    st.session_state.recording_deleted = True
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
        metric_rows = feed_metrics_rows(st.session_state.feed_events)
        st.download_button("Metriche del feed (CSV)", export_csv(metric_rows, FEED_METRIC_COLUMNS),
                           "feed_metrics.csv", "text/csv", disabled=not metric_rows)
