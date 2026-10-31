# Metriche comportamentali della Fase 1

Il tracciamento non cambia immagini, interfaccia, randomizzazione, numerosità, assegnazioni OLD/NEW o scoring. Il protocollo resta 30 volti nel feed (10 Real, 10 GAN, 10 Transformer, 5 F e 5 M per categoria) e 60 prove di memoria (30 OLD e 30 NEW). I metadati vengono dal manifest e restano sul server.

## Criterio temporale

Un'esposizione inizia quando **almeno il 75% dell'area dell'immagine** è visibile, l'immagine è stata decodificata, il documento è visibile e la finestra ha il focus. L'area visibile è l'intersezione tra immagine, viewport visiva e contenitori con clipping, incluso il contenitore scorrevole di Streamlit. Le immagini coperte dalle finestre della simulazione non vengono contate; un'immagine nel popup del post può essere contata per lo stesso post. Due elementi dello stesso post non producono due timer.

L'esposizione termina quando viene meno una delle condizioni: scrolling sotto soglia, immagine non disponibile, navigazione interna, overlay che copre la foto, perdita del focus, scheda nascosta o uscita dalla pagina. Il ritorno al post avvia una nuova esposizione. La soglia riguarda l'area effettiva dell'immagine e **non viene adattata all'altezza dello schermo**: su una finestra molto bassa può essere impossibile raggiungere il 75% e quindi la durata resta zero.

Questo criterio è indipendente da `post_impression`, che mantiene la regola preesistente del 60% dello spazio disponibile per abilitare Continua. Le impressioni non vengono convertite in tempi di visualizzazione. Uno zero nelle nuove durate non implica necessariamente che il partecipante non abbia mai visto una parte del volto.

Il clock usa `performance.now()`, monotono nel documento. Scrolling e ridimensionamento vengono osservati tramite eventi e IntersectionObserver; si controllano anche focus, visibilità del documento e viewport visiva mobile. Non si tratta di eye tracking né di una misura validata dell'attenzione.

## Esposizioni, checkpoint e rerun

Gli eventi individuali precedenti restano disponibili. Sono aggiunti:

| Evento | Contenuto |
|---|---|
| `feed_tracking_started` | Conferma che il tracker della sessione è stato avviato, versione 1 |
| `feed_view` | `exposure_id`, indice progressivo per post, timestamp di avvio, `duration_ms` cumulativa, `closed` e motivo |
| `feed_tracking_finalized` | Tutti i timer del feed sono stati chiusi prima di richiedere il riconoscimento |

Ogni esposizione ha un ID stabile. L'inizio, i checkpoint ogni 2 secondi e la chiusura aggiornano **la stessa esposizione**. Nell'aggregazione si prende la durata massima ricevuta per ID, senza sommare i checkpoint. La chiusura resta acquisita anche se un checkpoint precedente arriva in ritardo. Gli ID degli eventi vengono deduplicati nel database e nell'aggregazione.

Il tracker vive al di fuori dei normali aggiornamenti del componente e viene riutilizzato per la stessa `session_id`. I rerun non azzerano il clock e non aprono nuove esposizioni se la foto resta sufficientemente visibile. La sostituzione del DOM durante il rendering non viene interpretata come una nuova esposizione.

Le immagini del feed vengono conservate in una cache per sessione nel browser: dopo la conferma di avvio del tracker il server non reinvia tutte le immagini a ogni checkpoint. Il percorso di caricamento del riconoscimento resta quello precedente.

Gli eventi non ancora confermati dal server sono conservati in un outbox nella `sessionStorage` della scheda e reinviati durante il ricollegamento del componente. Gli eventi confermati vengono rimossi dall'outbox. Se lo storage del browser è bloccato rimane la coda in memoria; lo storage non contiene immagini o la soluzione del riconoscimento. Il database conserva gli eventi solo dopo la transazione SQLite riuscita.

Checkpoint e outbox riducono il rischio di perdita, ma la chiusura forzata del browser, un arresto del dispositivo o una disconnessione definitiva possono impedire la consegna degli ultimi dati. L'intervallo di 2 secondi è una cadenza prevista, soggetta alla schedulazione del browser. `pagehide`, blur e scheda nascosta tentano la chiusura immediata. Non si ricostruiscono i tempi mancanti usando l'orario del server.

## Calcolo di `feed_metrics.csv`

La fonte dell'elenco completo dei post è l'assegnazione della sessione (`session_started.details.post_order` e snapshot dei metadati). Per ogni sessione vengono prodotte **30 righe**, una per ogni post assegnato al feed, incluse le immagini mai sufficientemente visibili. Le 30 immagini NEW del riconoscimento non hanno una riga di Fase 1.

Per le durate delle esposizioni distinte `d1, …, dn`, ordinate per indice di esposizione:

| Campo | Definizione |
|---|---|
| `total_view_duration_ms` | Somma delle durate delle esposizioni |
| `first_view_duration_ms` | Durata della prima esposizione, anche se breve |
| `view_count` | Numero di ID di esposizione distinti |
| `mean_view_duration_ms` | Totale diviso per view_count, arrotondato a 3 decimali |
| `max_view_duration_ms` | Durata dell'esposizione più lunga |

Se il tracker è stato avviato e finalizzato e non esistono esposizioni per un post, tutti questi valori sono **0**, con `metrics_missing=0`. Gli inizi con durata iniziale zero sono esposizioni effettive solo se la soglia è stata raggiunta, non semplici impressioni.

Le durate restano **vuote**, con `metrics_missing=1`, se la strumentazione non era disponibile (ad esempio sessioni precedenti alla modifica), se manca la finalizzazione o se un'esposizione ricevuta non risulta chiusa. `metrics_status` distingue `complete`, `incomplete` e `unavailable`; `feed_finalized` indica la presenza dell'evento di chiusura e `tracking_version` la versione osservata. I valori mancanti non vengono sostituiti con zero. Le sessioni senza registro di assegnazione non possono avere righe inventate per post mai osservati.

### Interazioni

Gli stati finali sono calcolati dagli eventi della Fase 1, in ordine di registrazione. Gli eventi di memoria non modificano le metriche del feed.

| Campo | Definizione |
|---|---|
| `liked` | Stato finale Like, 0/1 |
| `like_count`, `unlike_count` | Attivazioni e rimozioni del Like, incluse le rimozioni automatiche quando si seleziona Dislike |
| `disliked` | Stato finale Dislike, 0/1; il pulsante era già presente |
| `dislike_count`, `remove_dislike_count` | Attivazioni e rimozioni del Dislike |
| `saved` | Stato finale del salvataggio, 0/1, dopo save/unsave |
| `comment_open_count` | Aperture tramite Commenta più espansioni dei commenti |
| `comment_count` | Commenti effettivamente inviati con testo non vuoto; digitazione e invio vuoto non contano |
| `shared_count` | Condivisioni simulate confermate (`share_confirmed`); nel feed attuale è sempre 0 perché non esiste un comando di condivisione |
| `interaction_count` | Numero complessivo di azioni social distinte |

Ogni azione social ha un `action_id`. Se un clic su Dislike rimuove il Like, si mantengono entrambi gli eventi, ma si conta una sola azione in `interaction_count`. Il doppio clic sull'immagine conta un'attivazione Like solo quando cambia lo stato. Aperture dei commenti, invii, salvataggi/rimozioni e reazioni/rimozioni sono azioni; impressioni, checkpoint, retry dell'immagine e navigazione non lo sono. Negli eventi storici senza action_id si usa l'ID dell'evento e non si tenta di ricostruire raggruppamenti assenti.

### Identificativi e categoria

Ogni riga include `participant_id`, `session_id`, `stimulus_id`, `post_id`, `filename`, `gender` e `feed_position` (1–30 nell'ordine effettivo della sessione).

Nel nuovo dataset `stimulus_type` contiene **Real/GAN/Transformer** e `source_type` conserva i valori canonici **real/gan/transformer** del manifest. Nel registro eventi preesistente la colonna `stimulus_type` mantiene il raggruppamento storico real/deepfake per compatibilità; usare `source_type` per distinguere le tre categorie in entrambi i dataset. Nessuna categoria viene dedotta da didascalie o nomi del profilo.

## Disponibilità e collegamento alla memoria

L'Area ricercatore autenticata offre **Metriche del feed (CSV)**, con nome file `feed_metrics.csv`. Il download utilizza i filtri di partecipante, sessioni e completamento; il filtro Fase non lo priva degli eventi necessari della Fase 1. Il registro eventi e tutti gli export precedenti rimangono disponibili.

L'export definitivo è disponibile dopo la chiusura dei timer al termine del feed, prima del passaggio alle istruzioni di memoria. Le sessioni ancora aperte o interrotte non vengono esportate come definitive: i checkpoint restano nel registro completo CSV/JSON. Le sessioni storiche già passate alla memoria possono essere esportate con durate mancanti esplicitamente segnalate. L'aggregatore Python consente anche righe diagnostiche incomplete con `feed_metrics_rows(events, finalized_only=False)`, che non sono presentate come misure definitive.

Il join con le risposte di memoria usa **participant_id + session_id + stimulus_id**, senza modificare il test. Tutti i 30 OLD possono corrispondere alle 30 righe del feed; i 30 NEW sono nuovi per definizione e non hanno metriche di esposizione precedente. La loro assenza nel join non va convertita in zero come se fossero post del feed mai visualizzati.

Esempio facoltativo con pandas, senza aggiungere dipendenze all'app:

```python
import pandas as pd

memory = pd.read_csv("instalab_memoria.csv")
feed = pd.read_csv("feed_metrics.csv")
joined = memory.merge(feed, on=["participant_id", "session_id", "stimulus_id"],
                      how="left", validate="one_to_one", suffixes=("_memory", "_feed"), indicator=True)
old = joined[joined["target"] == "OLD"]
# Verificare metrics_missing e la riuscita del join prima di analizzare le durate.
```

## Verifiche

`python -m unittest discover -s tests` controlla formule, checkpoint duplicati/fuori ordine, stati social, separazione per sessione/fase, zeri e dati mancanti. Con Playwright e Chromium, `python tests/browser_feed_metrics.py` verifica desktop e mobile: soglia 75%, immagine completamente fuori viewport, ritorni, focus, visibilità della scheda, rerun, azioni social e finalizzazione. `browser_continue.py` e `browser_images.py` mantengono i controlli della procedura e delle immagini. I controlli automatici di blur/visibilità emettono anche eventi di ciclo di vita simulati, senza pretendere di validare ogni browser o sistema operativo.
