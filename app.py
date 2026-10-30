"""Streamlit + Prolific starter: a demo news-rating experiment.

Deploy on Streamlit Community Cloud using requirements.txt.
Demo mode works without credentials and does not save data remotely.
Real Prolific sessions require configured Supabase secrets.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from uuid import uuid4

import requests
import streamlit as st


st.set_page_config(
    page_title="Esperimento sulle notizie — Demo",
    page_icon="📰",
    layout="centered",
)

# ONLY DEMONSTRATION STIMULI. Replace before running a real study.
NEWS_ITEMS = [
    {
        "id": "N01",
        "title": "Una biblioteca comunale sperimenta un orario di apertura esteso",
        "text": "Secondo la notizia, la biblioteca starebbe valutando l'apertura serale "
                "in alcuni giorni della settimana per favorire gli studenti.",
        "source": "Notizie Locali — DEMO",
    },
    {
        "id": "N02",
        "title": "Un ateneo prova un sistema digitale per prenotare gli spazi studio",
        "text": "Il progetto descritto prevede una piattaforma che permetterebbe agli "
                "studenti di verificare la disponibilità delle postazioni.",
        "source": "Campus Oggi — DEMO",
    },
    {
        "id": "N03",
        "title": "Una città avvia un progetto pilota per misurare i flussi di traffico",
        "text": "L'amministrazione, secondo la notizia, intenderebbe usare sensori "
                "per analizzare gli spostamenti nelle ore di maggiore affluenza.",
        "source": "Città e Dati — DEMO",
    },
    {
        "id": "N04",
        "title": "Un museo annuncia visite serali in alcune date sperimentali",
        "text": "La notizia presenta un calendario pilota di aperture serali "
                "con percorsi guidati rivolti a un pubblico più ampio.",
        "source": "Cultura Aperta — DEMO",
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def secret(name: str) -> str:
    """Read deployment secrets; support an unconfigured local/demo app."""
    try:
        value = st.secrets.get(name, "")
    except (FileNotFoundError, KeyError):
        return ""
    return str(value).strip() if value is not None else ""


def save_to_supabase(record: dict) -> None:
    """Save only on Streamlit's server; never ship the secret key to users."""
    url = secret("SUPABASE_URL").rstrip("/")
    api_key = secret("SUPABASE_SECRET_KEY")
    if not url or not api_key:
        raise RuntimeError("Database non configurato nelle Secrets di Streamlit.")

    endpoint = f"{url}/rest/v1/study_responses"
    headers = {
        "apikey": api_key,  # sb_secret_* keys are NOT JWT bearer tokens
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    response = requests.post(endpoint, json=record, headers=headers, timeout=15)
    response.raise_for_status()


query_pid = str(st.query_params.get("PROLIFIC_PID", "")).strip()
query_study_id = str(st.query_params.get("STUDY_ID", "")).strip()
query_session_id = str(st.query_params.get("SESSION_ID", "")).strip()

# Preview without Prolific (or with a fake TEST* PID): not remotely saved.
demo_mode = not query_pid or query_pid.upper().startswith("TEST")

if "stage" not in st.session_state:
    st.session_state.stage = "intro"
if "demo_id" not in st.session_state:
    st.session_state.demo_id = f"DEMO-{uuid4().hex[:10]}"
if "condition" not in st.session_state:
    if demo_mode:
        st.session_state.condition = secrets.choice(("visible", "hidden"))
    else:
        # Stable allocation for the same participant in this demo (roughly 50/50).
        digest = hashlib.sha256(f"demo-news-v1:{query_pid}".encode()).digest()
        st.session_state.condition = ("visible", "hidden")[digest[0] % 2]

st.title("Valutazione di notizie")
st.caption("Prototipo sperimentale in Streamlit · 4 notizie dimostrative")

if demo_mode:
    st.info("**Modalità DEMO.** Puoi provare lo studio subito. I dati non vengono salvati online: alla fine puoi esportare un file JSON.")
else:
    st.caption("Sessione Prolific riconosciuta automaticamente.")
    if not (secret("SUPABASE_URL") and secret("SUPABASE_SECRET_KEY")):
        st.error("Il database dello studio non è ancora configurato. Non iniziare lo studio reale: contatta il ricercatore.")
        st.stop()

if st.session_state.stage == "intro":
    st.subheader("Informazioni e consenso")
    st.write(
        "In questa dimostrazione ti saranno presentate quattro brevi notizie "
        "inventate per verificare il funzionamento dell'interfaccia. "
        "Per ciascuna notizia indicherai la credibilità percepita "
        "e la probabilità che tu decida di leggerla."
    )
    st.write(
        "In uno studio reale questa schermata deve essere sostituita "
        "dalle informazioni approvate dal comitato etico: responsabili, "
        "finalità, trattamento dati, contatti e diritto al ritiro."
    )
    consent = st.checkbox("Ho letto le informazioni e accetto di partecipare a questa prova.")
    if st.button("Inizia la prova", type="primary", disabled=not consent, use_container_width=True):
        st.session_state.started_at = now_iso()
        st.session_state.stage = "task"
        st.rerun()

elif st.session_state.stage == "task":
    st.progress(0.5, text="Compila le valutazioni e poi premi Invia risposte")
    with st.form("news_form", clear_on_submit=False):
        for index, item in enumerate(NEWS_ITEMS, start=1):
            with st.container(border=True):
                st.markdown(f"#### Notizia {index} di {len(NEWS_ITEMS)}")
                if st.session_state.condition == "visible":
                    st.caption(f"Fonte: {item['source']}")
                st.write(f"**{item['title']}**")
                st.write(item["text"])
                st.radio(
                    "Quanto ritieni credibile questa notizia? (1 = per niente, 7 = moltissimo)",
                    options=list(range(1, 8)),
                    index=None,
                    horizontal=True,
                    key=f"cred_{index}",
                )
                st.radio(
                    "Quanto saresti propenso/a a cliccare per leggere l'articolo? (1–7)",
                    options=list(range(1, 8)),
                    index=None,
                    horizontal=True,
                    key=f"click_{index}",
                )
        submitted = st.form_submit_button("Invia risposte", type="primary", use_container_width=True)

    if submitted:
        incomplete = [i for i in range(1, len(NEWS_ITEMS) + 1)
                      if st.session_state.get(f"cred_{i}") is None
                      or st.session_state.get(f"click_{i}") is None]
        if incomplete:
            st.warning("Completa entrambe le valutazioni per tutte e quattro le notizie.")
        else:
            responses = [
                {
                    "item_id": item["id"],
                    "credibility": st.session_state[f"cred_{i}"],
                    "click_likelihood": st.session_state[f"click_{i}"],
                }
                for i, item in enumerate(NEWS_ITEMS, start=1)
            ]
            submitted_at = now_iso()
            duration_seconds = int(
                (datetime.fromisoformat(submitted_at)
                 - datetime.fromisoformat(st.session_state.started_at)).total_seconds()
            )
            record = {
                "response_key": (
                    f"{query_study_id or 'STUDY'}:{query_session_id or query_pid}"
                    if not demo_mode else st.session_state.demo_id
                ),
                "prolific_pid": query_pid if not demo_mode else st.session_state.demo_id,
                "study_id": query_study_id or "DEMO-STUDY",
                "prolific_session_id": query_session_id or None,
                "condition": "source_visible" if st.session_state.condition == "visible" else "source_hidden",
                "started_at": st.session_state.started_at,
                "submitted_at": submitted_at,
                "duration_seconds": duration_seconds,
                "answers": responses,
            }
            st.session_state.record = record
            if demo_mode:
                st.session_state.stage = "done"
                st.rerun()
            else:
                try:
                    with st.spinner("Salvataggio delle risposte in corso..."):
                        save_to_supabase(record)
                except requests.HTTPError as error:
                    if error.response is not None and error.response.status_code == 409:
                        st.error("Una risposta con questo codice di sessione risulta già presente. Contatta il ricercatore prima di riprovare.")
                    else:
                        st.error("Impossibile salvare le risposte. Riprova oppure contatta il ricercatore.")
                except (requests.RequestException, RuntimeError):
                    st.error("Connessione al database non riuscita. Riprova: la partecipazione non è ancora registrata.")
                else:
                    st.session_state.stage = "done"
                    st.rerun()

elif st.session_state.stage == "done":
    st.success("Prova completata. Grazie per la partecipazione!")
    if demo_mode:
        st.write("Puoi verificare i risultati prodotti in questa sessione:")
        st.json(st.session_state.record, expanded=False)
        st.download_button(
            "Scarica le risposte DEMO (JSON)",
            data=json.dumps(st.session_state.record, ensure_ascii=False, indent=2),
            file_name="risposte_demo.json",
            mime="application/json",
            use_container_width=True,
        )
    else:
        st.write("Le tue risposte sono state salvate.")
        completion_url = secret("PROLIFIC_COMPLETION_URL")
        if completion_url:
            st.link_button("Torna su Prolific per completare lo studio", completion_url, type="primary", use_container_width=True)
        else:
            st.warning("URL di completamento Prolific non ancora impostato. Contatta il ricercatore per ricevere il codice di completamento.")
