# InstaLab — simulazione di feed social per ricerca

Un feed **ispirato visivamente a Instagram**, realizzato in Streamlit con un componente personalizzato HTML/CSS/JavaScript. Non è Instagram e non usa account, API o dati del social network.

## Files

- `app.py`: ingresso Streamlit, gestione dei contenuti e registrazione degli eventi su SQLite.
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

### Provare il feed / scaricare il log della sessione

- Apri l'indirizzo dell'app per usare il feed.
- Aggiungi `?preview=1` all'indirizzo per aprire il **pannello ricercatore** e scaricare un CSV degli eventi della sessione corrente.
- Puoi testare la lettura del parametro Prolific con `?PROLIFIC_PID=TEST001&preview=1`.
- Gli eventi riportano `event_type`, `post_id`, `stimulus_id`, `stimulus_type`, ora del client e tempo approssimato trascorso.

## Funzionalità della versione 1

- Feed centrato e responsive, senza pannelli laterali o navigazione mobile.
- Storie cliccabili e visualizzatore.
- Like e rimozione Like, anche con doppio clic sull'immagine.
- Inserimento commenti (visibili all'interno della propria sessione).
- Dislike e rimozione dislike, alternativi al like; salvataggio dei post. Nessun invio o condivisione.
- Ricerca, Esplora, Profilo, visualizzazione di post in popup.
- Registrazione degli eventi su SQLite + esportazione CSV della sessione nel pannello ricercatore.

## IMPORTANTE prima di reclutare persone su Prolific

Questa è una **demo di interfaccia**, non uno strumento di ricerca pronto per il campo:

1. Gli eventi vengono salvati in SQLite sul disco del server. Un disco effimero, come quello di Streamlit Community Cloud, non garantisce la conservazione dopo riavvii infrastrutturali o redeploy: per la raccolta reale configurare storage durevole e backup.
2. È presente un consenso preliminare con informazioni ancora da completare. Non ci sono ancora assegnazione sperimentale o ritorno con completion code a Prolific.
3. Le misure dei tempi e delle impressioni del feed sono approssimative, non validate per test cognitivi con timing preciso.
4. Le immagini demo sono segnaposto. Verifica le autorizzazioni d'uso dei tuoi stimoli prima della pubblicazione.
5. Il feed è una simulazione, senza accesso o connessione a Instagram.
6. Si raccomanda di evitare che `PROLIFIC_PID` sia esposto o condiviso accidentalmente nei file esportati.

Per uno studio reale, completare consenso e procedure di privacy, configurare conservazione durevole e backup e validare il protocollo e il logging sul deployment scelto.

## Registrazione delle interazioni

L'app salva gli eventi (like, rimozione del like, dislike, rimozione del dislike, commenti e impressioni) in `.local-data/events.sqlite3`, fuori dai file versionati. Non sono inviati a Instagram. Ogni evento include sessione, `PROLIFIC_PID` se presente, post, stimolo e orario di ricezione del server. All'inizio vengono salvati anche timestamp del consenso e ordine dei post. I reinvii dello stesso evento non creano duplicati e due sessioni senza PID hanno identificativi distinti.

Per scegliere un disco persistente, impostare `INSTALAB_DB_PATH` sul percorso completo del database **prima dell'avvio**. Il percorso è una configurazione del server, mai un parametro della pagina. Il salvataggio sopravvive alla chiusura della sessione e al riavvio del processo se il file resta sul disco; non sopravvive alla perdita di un disco effimero. Non è ancora configurato un database esterno. I dati di sessioni precedenti non vengono ripristinati nel browser di un altro partecipante.

Il pannello `?preview=1` esporta solo gli eventi della sessione corrente. Per esportare tutte le sessioni, dal terminale del server con lo stesso `INSTALAB_DB_PATH`:

```sh
python event_store.py --output /percorso/privato/interazioni.csv
```

Il database e gli export contengono dati di ricerca: conservarli fuori da Git e dalle cartelle pubbliche, limitare l'accesso e definire conservazione e backup prima del reclutamento. Errori di scrittura non vengono conteggiati come salvataggi riusciti: la pagina offre un pulsante per riprovare. Non chiudere la pagina finché il problema non è risolto.

Il feed non offre più condivisione, invio o copia di link dei post. `anteprima.html` resta una dimostrazione frontend senza backend: per registrare gli eventi avviare `app.py` con Streamlit.

## Fase di memoria OLD/NEW

La pagina iniziale non anticipa il compito di memoria. Dopo aver scorso i 20 volti del feed con like/dislike, il pulsante **Continua** apre le istruzioni del riconoscimento. Il pulsante è disponibile quando le 20 visualizzazioni sono state registrate sul server: immagine caricata e almeno il 60% dello spazio disponibile per la fotografia visibile (altezza della fotografia oppure del viewport, se inferiore). Il conteggio non richiede di mostrare il 60% di un intero post, che potrebbe essere impossibile su finestre basse. Il contatore a fine feed indica le visualizzazioni già confermate dal server; se manca un volto, **Mostra il prossimo volto da visualizzare** lo riporta al centro dello schermo. Il tracciamento viene ricollegato dopo like, commenti e chiusura dei popup. Non è necessario mettere una reazione a ogni post.

Da **Inizia il riconoscimento** si passa a 20 prove, una fotografia per volta, con lo stesso stile del feed e due pulsanti al posto delle reazioni:

- **OLD — Già visto**: volto presente nel feed precedente.
- **NEW — Nuovo**: volto non presente nel feed precedente.

Per sessione vengono estratti casualmente 10 OLD dai 20 volti della prima fase (5 reali e 5 sintetici), mescolati con 10 NEW (5 reali e 5 sintetici) definiti in `recognition_new_posts` in `posts.json`. I NEW non vengono mostrati né precaricati nella prima fase. Il piano viene fissato e salvato all'avvio della sessione. Gli ID delle prove visualizzati nel browser non indicano OLD/NEW e non si riutilizzano nomi, commenti o conteggi del feed come indizi di riconoscimento.

Ogni prova accetta una sola scelta. La prova successiva compare dopo il salvataggio; non viene mostrato un feedback di correttezza. Le risposte e l'evento di completamento usano lo stesso database e la stessa sessione/PID della prima fase. La confidenza non è implementata.

Negli export CSV sono presenti `phase`, `trial_id`, `response`, `target`, `correct`, `response_time_ms` e `displayed_client_ts`, oltre a post, stimolo e timestamp server. La correttezza viene calcolata dal server rispetto al piano di presentazione. Il tempo di risposta è una stima nel browser dal caricamento/visualizzazione dell'immagine al clic, non una misura validata per esperimenti di timing preciso; include eventuali interruzioni o schede in background. L'app non garantisce persistenza della sessione del browser dopo refresh o chiusura, né ripresa autenticata dal PID.

È un protocollo provvisorio: proporzioni, bilanciamento, definizione di esposizione, tempi e familiarità delle fotografie vanno validati prima del reclutamento. Le istruzioni non dichiarano autorizzazioni etiche, durate o condizioni di conservazione non configurate.

## Controlli di sviluppo

Eseguire `python -m unittest discover -s tests`. Con Playwright e Chromium disponibili, `python tests/browser_continue.py` verifica il tracciamento su finestre basse, dopo like/commenti, il recupero dei volti mancanti e il segnale di Continua. `CHROMIUM_PATH` può indicare un eseguibile Chromium diverso.

## Caricamento delle immagini

Gli originali rimangono invariati. `image_assets.py` genera in memoria versioni WebP di visualizzazione (qualità 92, lato massimo 960 px, orientamento EXIF rispettato), con cache limitata e invalidata quando il file cambia. I riquadri sintetici vengono ritagliati dal foglio sorgente sul server: il browser riceve singoli volti, senza dover ridimensionare e mascherare un foglio da 3664×1951 pixel in ogni post. Si applica lo stesso percorso di preparazione ai volti reali e sintetici; OLD e prima fase usano la stessa derivata. La compressione e le dimensioni di questa demo vanno validate per l'uso sperimentale.

Nel campione corrente le immagini del feed passano da circa 6,7 MB di sorgenti uniche a 1,4 MB di derivate (prima della codifica base64). Il tempo effettivo dipende da connessione e dispositivo; la prima preparazione sul server richiede più tempo di quelle successive già in cache.

Il feed avvia il caricamento di tutti i 20 volti; il riconoscimento precarica solo i due volti successivi della seconda fase. Gli aggiornamenti del feed mantengono gli elementi immagine già decodificati. Un errore mostra **Riprova caricamento** e blocca le reazioni finché l'immagine non è disponibile. Le visualizzazioni e il tempo di risposta al riconoscimento iniziano solo dopo la decodifica.

`image_position` in `posts.json` corregge l'inquadratura nel riquadro quadrato: per alcune fotografie verticali è impostato `center top`, così il volto non viene tagliato dal centraggio sul busto. La stessa impostazione vale per l'eventuale ripresentazione OLD.

Con Playwright e Pillow nello stesso runtime, `python tests/browser_images.py` controlla tutti i volti, scorrimenti ripetuti, conservazione degli elementi immagine attraverso aggiornamenti, e recupero da un errore di decodifica simulato. L'anteprima HTML include le stesse immagini ottimizzate; il salvataggio degli eventi resta disponibile solo tramite Streamlit.
