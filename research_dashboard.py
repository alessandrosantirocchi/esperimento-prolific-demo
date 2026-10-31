"""Password-protected exports and explicit management of participant sessions."""

import hashlib
import hmac
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st
from feed_metrics import feed_metrics_rows, FEED_METRIC_COLUMNS
from streamlit.errors import StreamlitSecretNotFoundError

from event_store import read_events, delete_sessions
from export_data import csv_bytes, filter_events, final_reactions, REACTION_COLUMNS, REACTION_TYPES


def configured_password():
    password = os.environ.get("INSTALAB_RESEARCHER_PASSWORD")
    if not password:
        try:
            password = st.secrets.get("researcher_password")
        except (StreamlitSecretNotFoundError, FileNotFoundError):
            return None
    return password if (isinstance(password, str) and password.strip()
                        and password != "SOSTITUISCI_CON_UNA_PASSWORD_PRIVATA") else None


def fingerprint(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def authenticate():
    supplied = st.session_state.pop("research_password", "")
    password = configured_password()
    if time.monotonic() < st.session_state.get("research_locked_until", 0):
        return
    if password and hmac.compare_digest(supplied.encode("utf-8"), password.encode("utf-8")):
        st.session_state.research_auth = fingerprint(password)
        st.session_state.research_login_error = False
        st.session_state.research_attempts = 0
    else:
        st.session_state.research_login_error = True
        attempts = st.session_state.get("research_attempts", 0) + 1
        st.session_state.research_attempts = attempts
        if attempts >= 5:
            st.session_state.research_locked_until = time.monotonic() + 60
            st.session_state.research_attempts = 0


def logout():
    for key in list(st.session_state):
        if key.startswith("research_"):
            del st.session_state[key]


def _clear_deletion():
    st.session_state.pop("research_pending_delete", None)
    st.session_state.pop("research_delete_confirmation", None)


@st.dialog("Conferma eliminazione", dismissible=False)
def confirm_deletion(session_ids):
    # Dialog interactions run separately: recheck access before reading or deleting.
    password = configured_password()
    if not password or not hmac.compare_digest(st.session_state.get("research_auth", ""), fingerprint(password)):
        logout()
        st.rerun()
    if st.button("Annulla"):
        _clear_deletion()
        st.rerun()
    try:
        selected = [e for e in read_events() if e["session_id"] in set(session_ids)]
    except (sqlite3.Error, OSError, ValueError):
        st.error("Non è stato possibile verificare i dati. Annulla e riprova.")
        return
    if not selected:
        st.info("Le sessioni selezionate non sono più presenti nel database.")
        return
    count = len({e["session_id"] for e in selected})
    st.warning(f"Stai per eliminare definitivamente {count} sessioni e {len(selected)} eventi, comprese risposte, reazioni e metadati. L'app non offre un annullamento dopo l'eliminazione.")
    st.code("\n".join(session_ids), language=None)
    st.download_button("Scarica una copia prima di eliminare (JSON)", json.dumps(selected, ensure_ascii=False, indent=2).encode("utf-8"), "instalab_sessioni_prima_eliminazione.json", "application/json")
    with st.form("research_delete_form"):
        confirmation = st.text_input("Scrivi ELIMINA per confermare", key="research_delete_confirmation")
        submitted = st.form_submit_button("Elimina definitivamente", type="primary")
    if submitted:
        if confirmation != "ELIMINA":
            st.error("Per eliminare queste sessioni, scrivi esattamente ELIMINA.")
            return
        try:
            result = delete_sessions(list(session_ids))
        except (sqlite3.Error, OSError, ValueError):
            st.error("Eliminazione non riuscita. Riprova; nessuna cancellazione parziale è stata applicata.")
            return
        st.session_state.research_delete_notice = result
        st.session_state.pop("research_delete_sessions", None)
        _clear_deletion()
        st.rerun()


def render_deletion(events, filtered):
    with st.expander("Elimina sessioni di prova"):
        st.write("Seleziona esplicitamente le sessioni da cancellare. La cancellazione riguarda l'intera sessione, anche se hai filtrato una sola fase. Nessuna selezione significa nessuna cancellazione.")
        available = {e["session_id"] for e in filtered}
        if not available:
            st.caption("Nessuna sessione disponibile con i filtri attuali.")
            return
        labels = {}
        for session_id in available:
            rows = [e for e in events if e["session_id"] == session_id]
            timestamp = min((e.get("server_received_ts", "") for e in rows if e.get("server_received_ts")), default="")
            try:
                started = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                label_time = started.astimezone(ZoneInfo("Europe/Rome")).strftime("%d/%m/%Y %H:%M:%S")
            except ValueError:
                label_time = "Data non disponibile"
            labels[session_id] = f"{label_time} · {rows[0].get('participant_id', '')} · {session_id[:8]} · {len(rows)} eventi"
        options = sorted(available, key=lambda s: labels[s], reverse=True)
        if st.button("Seleziona tutte le sessioni mostrate"):
            st.session_state.research_delete_sessions = options
        previous = st.session_state.get("research_delete_sessions", [])
        if not set(previous) <= available:
            st.session_state.research_delete_sessions = [s for s in previous if s in available]
        selected = st.multiselect("Sessioni da eliminare", options, format_func=lambda s: labels[s],
                                  placeholder="Scegli le singole sessioni", key="research_delete_sessions")
        st.caption("Le date sono nell'orario di Roma. Lo stesso ID partecipante può avere più sessioni indipendenti.")
        if st.button("Elimina le sessioni selezionate", disabled=not selected):
            st.session_state.research_pending_delete = tuple(selected)
    if st.session_state.get("research_pending_delete"):
        confirm_deletion(st.session_state.research_pending_delete)


def render_dashboard():
    st.title("Area ricercatore")
    st.caption("Risposte dei partecipanti · Esportazione dei dati salvati sul server")
    password = configured_password()
    if password is None:
        logout()
        st.info("Accesso non ancora configurato. Nei Secrets dell'app Streamlit imposta la chiave researcher_password con una password privata, poi riapri questa pagina. Non inserire la password nell'indirizzo o in GitHub.")
        return
    authorized = hmac.compare_digest(st.session_state.get("research_auth", ""), fingerprint(password))
    if not authorized:
        st.session_state.pop("research_auth", None)
        _clear_deletion()
        st.write("Accedi per consultare ed esportare le risposte di più sessioni.")
        locked = time.monotonic() < st.session_state.get("research_locked_until", 0)
        with st.form("research_login"):
            st.text_input("Password ricercatore", type="password", key="research_password")
            st.form_submit_button("Accedi", on_click=authenticate, disabled=locked)
        if locked:
            st.warning("Troppi tentativi. Attendi un minuto e ricarica la pagina.")
        elif st.session_state.get("research_login_error", False):
            st.error("Password non corretta.")
        return

    actions = st.columns(2)
    with actions[0]:
        if st.button("Aggiorna dati"):
            st.rerun()
    with actions[1]:
        st.button("Esci dall'area ricercatore", on_click=logout)

    try:
        events = read_events()
    except (sqlite3.Error, OSError, ValueError):
        st.error("Non è stato possibile leggere il database. Riprova con Aggiorna dati; i file non sono stati modificati.")
        return
    notice = st.session_state.pop("research_delete_notice", None)
    if notice:
        st.success(f"Eliminazione completata. Sessioni: {notice['sessions']} · Eventi: {notice['events']}.")
    with st.expander("Conservazione dei dati"):
        st.write("Questa sezione esporta i dati presenti nel database locale. L'eliminazione è disponibile solo nella sezione dedicata, dopo selezione e conferma. Non si recuperano sessioni da server precedenti o database già persi.")
        st.write("Su Streamlit Community Cloud il disco locale non garantisce conservazione dopo ricreazioni o redeploy. Prima della raccolta reale serve un database o un disco persistente con backup.")
    if not events:
        st.info("Nessuna risposta registrata nel database di questo server.")
        return

    participants = sorted({e.get("participant_id", "") for e in events})
    first, second = st.columns(2)
    with first:
        participant = st.selectbox("Partecipante", [None] + participants,
                                   format_func=lambda value: "Tutti i partecipanti" if value is None else value,
                                   key="research_participant")
        participant_events = filter_events(events, participant_id=participant)
        sessions = sorted({e["session_id"] for e in participant_events})
        if not set(st.session_state.get("research_sessions", [])) <= set(sessions):
            st.session_state.research_sessions = [s for s in st.session_state.research_sessions if s in sessions]
        selected_sessions = st.multiselect("Sessioni", sessions, key="research_sessions",
                                           placeholder="Tutte le sessioni",
                                           help="Nessuna selezione include tutte le sessioni del partecipante scelto.")
    with second:
        phase = st.selectbox("Fase", [None, "feed", "recognition"],
                             format_func=lambda value: {None: "Tutte le fasi", "feed": "Prima fase · like/dislike", "recognition": "Seconda fase · memoria"}[value],
                             key="research_phase")
        completed = st.checkbox("Solo sessioni con riconoscimento completato", key="research_completed")

    filtered = filter_events(events, participant, selected_sessions, phase, completed)
    selected_events = filter_events(events, participant, selected_sessions, None, completed)
    feed_rows = feed_metrics_rows(selected_events)
    memory = [e for e in filtered if e.get("event_type") == "recognition_response"]
    reactions = [e for e in filtered if e.get("event_type") in REACTION_TYPES]
    final = final_reactions(filtered)
    metrics = st.columns(3)
    metrics[0].metric("Sessioni selezionate", len({e["session_id"] for e in filtered}))
    metrics[1].metric("Risposte OLD/NEW", len(memory))
    metrics[2].metric("Eventi like/dislike", len(reactions))
    if not filtered:
        st.info("Nessun dato corrisponde ai filtri selezionati.")

    st.subheader("Scarica le risposte")
    st.caption("I download includono tutti i dati corrispondenti ai filtri, anche quelli non visibili nell'anteprima.")
    left, right = st.columns(2)
    with left:
        st.download_button("Risposte OLD/NEW (CSV)", csv_bytes(memory), "instalab_memoria.csv", "text/csv", disabled=not memory)
        st.download_button("Reazioni finali per volto (CSV)", csv_bytes(final, REACTION_COLUMNS), "instalab_reazioni_finali.csv", "text/csv", disabled=not final)
    with right:
        st.download_button("Registro like/dislike (CSV)", csv_bytes(reactions), "instalab_reazioni_eventi.csv", "text/csv", disabled=not reactions)
        st.download_button("Registro completo (CSV)", csv_bytes(filtered), "instalab_eventi.csv", "text/csv", disabled=not filtered)
    st.download_button("Copia dei dati filtrati (JSON)", json.dumps(filtered, ensure_ascii=False, indent=2).encode("utf-8"), "instalab_dati.json", "application/json", disabled=not filtered)
    st.download_button("Metriche del feed (CSV)", csv_bytes(feed_rows, FEED_METRIC_COLUMNS),
                       "feed_metrics.csv", "text/csv", disabled=not feed_rows)
    st.caption("Le metriche del feed riguardano le sessioni selezionate, indipendentemente dal filtro Fase. Il file definitivo è disponibile dopo la finalizzazione del feed; le sessioni ancora in corso restano nel registro eventi. Dati temporali mancanti sono vuoti e segnalati da metrics_missing, distinti dagli zeri dei volti mai visualizzati.")
    st.caption("Le reazioni finali includono i volti con almeno una reazione: LIKE, DISLIKE oppure NONE se rimossa. I volti senza reazioni non compaiono in questo file. Il JSON conserva i valori testuali originali; nei CSV i testi che potrebbero essere interpretati come formule sono protetti.")

    st.subheader("Anteprima risposte di memoria")
    table = []
    for event in memory[:500]:
        details = event.get("details", {})
        table.append({"Partecipante": event.get("participant_id", ""), "Sessione": event["session_id"],
                      "Stimolo": event.get("stimulus_id", ""), "File": event.get("filename", ""),
                      "Categoria": event.get("source_type", ""), "Genere": event.get("gender", ""),
                      "Risposta": details.get("response", ""),
                      "Atteso": details.get("target", ""), "Corretta": details.get("correct", ""),
                      "Tempo stimato (ms)": details.get("response_time_ms", ""),
                      "Ricevuta dal server (UTC)": event.get("server_received_ts", "")})
    st.dataframe(table, width="stretch", hide_index=True)
    if len(memory) > 500:
        st.caption("Anteprima limitata alle prime 500 risposte. Il download include tutte le risposte filtrate.")
    render_deletion(events, filtered)
