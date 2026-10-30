# InstaLab — simulazione di feed social per ricerca

Un feed **ispirato visivamente a Instagram**, realizzato in Streamlit con un componente personalizzato HTML/CSS/JavaScript. Non è Instagram e non usa account, API o dati del social network.

## Files

- `app.py`: ingresso Streamlit, gestione dei contenuti e raccolta temporanea del log.
- `styles.css`: aspetto dell'interfaccia (colori, dimensioni, sidebar, versione smartphone).
- `feed.js`: componenti grafici e interazioni (Like, commenti, salvataggi, storie, ecc.).
- `posts.json`: configurazione di post, testi, autori, condizioni e stimoli.
- `demo_01.jpg` ... `demo_04.jpg`: **immagini di prova**, NON i tuoi stimoli deepfake.
- `requirements.txt`: versione compatibile di Streamlit.
- `anteprima.html`: anteprima autonoma del feed, da aprire in Chrome o Safari senza Streamlit.

## Aggiornare l'app esistente su GitHub (senza programmare)

1. Scarica e **decomprimi** lo ZIP.
2. Vai su `https://github.com/alessandrosantirocchi/esperimento-prolific-demo`.
3. Clicca **Add file → Upload files** nella pagina principale del repository.
4. Trascina **tutti i file contenuti nella cartella decompressa** sulla pagina di caricamento, non lo ZIP. Non serve la cartella `__pycache__`.
5. GitHub potrebbe indicare che `app.py` e `requirements.txt` esistono già: è previsto; carica le nuove versioni e clicca **Commit changes**.
6. Se l'app è già pubblicata su Streamlit Community Cloud, in genere si aggiornerà dopo il commit. Altrimenti, vai su `https://share.streamlit.io` → **Create app** → **Yup, I have an app**, poi Repository `alessandrosantirocchi/esperimento-prolific-demo`, Branch `main`, Main file path `app.py`, infine **Deploy**.

## Modificare a mano da GitHub

1. Apri il repository, clicca **posts.json** (o `styles.css` o `feed.js`).
2. Premi la **matita** (Edit this file).
3. Modifica il testo, poi premi **Commit changes**.
4. La modifica viene distribuita da Streamlit dopo il commit.

**Dove modificare:**

| Obiettivo | File |
|---|---|
| Modificare post, nomi, caption, ordine, numero di Like iniziali | `posts.json` |
| Sostituire immagini con foto reali/deepfake | carica foto nella radice del repository e cambia `image` in `posts.json` |
| Cambiare colori, font, dimensioni delle schede, layout mobile | `styles.css` |
| Cambiare i comportamenti di Like, commenti, pulsanti, storie | `feed.js` |
| Modificare lettura dei dati, ID Prolific, esportazione | `app.py` |

### Esempio: inserire una foto deepfake

Carica una foto chiamata `face_fake_01.jpg` in **GitHub → Add file → Upload files**. Poi, in `posts.json`, cambia il campo relativo a un post:

```json
"image": "face_fake_01.jpg",
"stimulus_id": "DF_001",
"stimulus_type": "deepfake"
```

Per una foto reale userai, ad esempio, `"stimulus_type": "real"`. Il campo `stimulus_type` è un'etichetta **interna** che non appare al partecipante ma viene esportata nei dati.

La radice del progetto deve contenere queste immagini in JPG/PNG/WEBP: non inserire percorso `assets/` in `posts.json` (questa demo cerca i file direttamente accanto a `app.py`).

### Provare il feed / scaricare log temporaneo

- Apri l'indirizzo dell'app per usare il feed.
- Aggiungi `?preview=1` all'indirizzo per aprire il **pannello ricercatore** e scaricare un CSV degli eventi della sessione corrente.
- Puoi testare la lettura del parametro Prolific con `?PROLIFIC_PID=TEST001&preview=1`.
- Gli eventi riportano `event_type`, `post_id`, `stimulus_id`, `stimulus_type`, ora del client e tempo approssimato trascorso.

## Funzionalità della versione 1

- Layout desktop (sidebar / feed / suggerimenti) e mobile (barra inferiore).
- Storie cliccabili e visualizzatore.
- Like e rimozione Like, anche con doppio clic sull'immagine.
- Inserimento commenti (visibili all'interno della propria sessione).
- Condivisione simulata, salvataggi, segui/non seguire.
- Ricerca, Esplora, Profilo, visualizzazione di post in popup.
- Tracking eventi dimostrativo (dati di sessione) + esportazione CSV nel pannello ricercatore.

## IMPORTANTE prima di reclutare persone su Prolific

Questa è una **demo di interfaccia**, non uno strumento di ricerca pronto per il campo:

1. I dati NON vengono salvati su database persistente: la sessione può andare perduta.
2. Non c'è ancora una pagina di consenso, assegnazione sperimentale o un ritorno con completion code a Prolific.
3. Le misure dei tempi e delle impressioni del feed sono approssimative, non validate per test cognitivi con timing preciso.
4. Le immagini demo sono segnaposto. Verifica le autorizzazioni d'uso dei tuoi stimoli prima della pubblicazione.
5. Il feed è una simulazione, senza accesso o connessione a Instagram.
6. Si raccomanda di evitare che `PROLIFIC_PID` sia esposto o condiviso accidentalmente nei file esportati.

Per uno studio reale, il prossimo passo è usare un database (es. Supabase), consenso, randomizzazione, procedure di privacy e test end-to-end del logging.
