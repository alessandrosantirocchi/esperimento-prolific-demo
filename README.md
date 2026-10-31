# InstaLab — feed social e riconoscimento di volti

Applicazione Streamlit con un feed ispirato a Instagram, reazioni like/dislike, commenti e successivo compito di memoria OLD/NEW. Non usa account, API o dati di Instagram. Il protocollo prevede 30 volti nel feed e 60 prove di memoria, con quote uguali per categoria e genere.

## Provare l'app in locale

Richiede Python 3.11 o successivo. Nel terminale, dalla cartella del repository:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python validate_stimuli.py
python -m streamlit run app.py
```

Su Windows usare `python` al posto di `python3` e attivare l'ambiente con `.venv\Scripts\Activate.ps1` in PowerShell.

Aprire l'indirizzo mostrato da Streamlit, senza aggiungere identificativi al link. Accettare il consenso, scorrere tutti i volti, premere **Continua**, leggere le istruzioni e avviare il riconoscimento. Per una nuova sessione ricaricare la pagina. Non è implementata la ripresa di una sessione interrotta.

### Raccolta tramite un link pubblico

Per una bacheca universitaria si può condividere il normale indirizzo pubblico dell'app, senza parametri di reclutamento, account o un codice da inserire. Alla prima apertura l'app assegna in sessione un `participant_id` casuale del tipo `P_…`, indipendente dai parametri dell'URL. Il codice resta invariato durante consenso, feed, memoria e normali rerun Streamlit. Un `session_id` distinto identifica la prova e rimane uguale nelle due fasi.

Nei CSV usare `participant_id` e `session_id` per distinguere le partecipazioni; aggiungere `stimulus_id` per unire metriche del feed e risposte di memoria. Non vengono richiesti nome, e-mail o matricola per assegnare il codice. Il codice identifica una partecipazione, non certifica una persona distinta: una nuova scheda o un refresh che avvia una nuova sessione assegna nuovi codici e non permette di rilevare da solo partecipazioni ripetute. Non è implementato un identificatore persistente del browser.

I risultati storici non vengono riscritti. Se durante un aggiornamento è ancora attiva una sessione già consenziente, viene conservato il suo identificativo precedente, evitando di dividere la stessa prova tra codici diversi.

Le prove locali registrano dati nello stesso modo delle altre sessioni. Per tenere un database di prova separato, impostare `INSTALAB_DB_PATH` prima dell'avvio, per esempio su macOS/Linux:

```sh
INSTALAB_DB_PATH="$PWD/.local-data/prove.sqlite3" python -m streamlit run app.py
```

## Catalogo degli stimoli

L'unica fonte degli stimoli è `stimuli.csv`, accanto ad `app.py`, con le immagini nella cartella `images/`. Non ci sono più immagini demo di ripiego. Gli originali non vengono modificati.

Il CSV deve essere UTF-8, con separatore virgola e queste intestazioni:

```csv
stimulus_id,filename,source_type,gender
REAL_F_001,REAL_F_001.png,real,F
```

| Colonna | Contenuto |
|---|---|
| `stimulus_id` | Identificativo univoco assegnato dal ricercatore |
| `filename` | Nome esatto del file, comprese maiuscole/minuscole ed estensione |
| `source_type` | `real`, `gan` oppure `transformer` |
| `gender` | Etichetta `F` oppure `M` indicata dal ricercatore |

Sono ammessi JPG/JPEG, PNG e WebP. Il percorso può essere un semplice nome, un percorso sotto `images/`, oppure includere il prefisso `images/`, per esempio `images/gruppo/volto.png`. Percorsi assoluti o che escono da `images/` non sono ammessi. I percorsi vengono risolti dalla posizione di `app.py`, indipendentemente dalla directory di avvio: non occorrono percorsi del computer del ricercatore su Streamlit Cloud.

Le etichette vengono lette dal CSV, senza dedurle dal nome o dall'aspetto del volto. Per sostituire gli stimoli, aggiornare insieme immagini e manifest e avviare nuove sessioni: l'app ferma una sessione già iniziata se rileva una modifica del catalogo.

### Verifica del catalogo

`python validate_stimuli.py` verifica intestazioni, valori obbligatori, categorie, genere, percorsi, file mancanti o illeggibili, ID duplicati, file ripetuti, contenuti identici e immagini con gli stessi pixel anche se ricodificate. Controlla inoltre la disponibilità dei volti nuovi e segnala immagini non elencate nel CSV. Esce con codice 1 in caso di errore; `--json` produce il rapporto strutturato. I controlli non riconoscono la stessa identità in fotografie differenti.

Catalogo verificato in questa modifica:

| Categoria | F | M | Totale |
|---|---:|---:|---:|
| real | 20 | 20 | 40 |
| gan | 20 | 20 | 40 |
| transformer | 40 | 40 | 80 |
| **Totale** | **80** | **80** | **160** |

Nessun file mancante, illeggibile, ripetuto o non elencato rilevato. L'app mostra un messaggio generale se la configurazione non è valida; il comando di verifica fornisce al ricercatore i dettagli senza mostrarli ai partecipanti.

## Selezione e procedura

Per ogni nuova sessione vengono estratti e fissati:

- **Feed:** 30 volti, 10 reali, 10 GAN e 10 transformer. Ogni categoria comprende 5 F e 5 M, in ordine casuale.
- **Riserva NEW:** 30 volti distinti da tutti quelli del feed, anche questi 10 reali, 10 GAN e 10 transformer, con 5 F e 5 M per categoria.
- **Riconoscimento:** 60 prove in ordine casuale, con tutti i 30 volti del feed ripresentati una volta come OLD e i 30 volti della riserva come NEW. Ciascuna combinazione categoria × OLD/NEW comprende 5 F e 5 M.

Il totale è di **90 presentazioni e 60 immagini distinte** per partecipante. La selezione e l'ordine variano casualmente tra sessioni; categorie e genere hanno quote fisse. La selezione resta stabile durante gli aggiornamenti della stessa sessione.

Dopo i 30 volti del feed restano **130 volti non presentati**, più dei 30 NEW necessari; 100 immagini non vengono utilizzate in quella sessione. Servono almeno 10 file distinti per ciascuna combinazione categoria/genere: 5 per il feed e 5 per i NEW, quindi almeno 60 file complessivi. Una carenza in una categoria non può essere compensata con un'altra. In caso di insufficienza la validazione blocca l'avvio, senza riutilizzare volti come NEW.

La versione del protocollo viene registrata nei metadati degli eventi di avvio e assegnazione del piano. Una sessione avviata con il vecchio schema viene fermata e richiede di ricaricare la pagina per iniziarne una nuova; i dati precedenti non vengono modificati.

Il consenso preliminare è obbligatorio. Le istruzioni di memoria appaiono dopo il feed. **Continua** diventa disponibile quando il server ha registrato tutte le visualizzazioni: fotografia decodificata e almeno il 60% dell'altezza disponibile per l'immagine visibile (il minimo tra altezza della fotografia e del viewport). **Mostra il prossimo volto da visualizzare** permette di recuperare una visualizzazione mancante. Non è obbligatoria una reazione a ogni post.

Il riconoscimento presenta una fotografia per volta e consente una sola risposta OLD/NEW, senza feedback di correttezza. La prova successiva arriva dopo il salvataggio. La confidenza non è implementata. Il codice partecipante e la sessione sono gli stessi delle due parti.

## Metadati ed esportazione

Per gli eventi riferiti a un volto e per le reazioni finali, gli export CSV/JSON includono `stimulus_id`, `filename`, `source_type` e `gender`. È mantenuta anche la colonna precedente `stimulus_type` (`real`/`deepfake`) per compatibilità con il raggruppamento binario. Gli eventi generali della sessione non hanno uno stimolo associato; le loro colonne restano vuote. I vecchi eventi salvati prima di questa modifica non vengono alterati e possono avere vuote le nuove colonne.

Questi metadati, i percorsi originali e la soluzione OLD/NEW non vengono inviati al componente del partecipante. Il feed usa ID e nomi di profilo neutri e immagini incorporate. All'avvio vengono salvati sul server il consenso, l'ordine dei post, il piano di memoria, la versione del protocollo, l'impronta del catalogo e i metadati dei 60 stimoli selezionati, con hash dei file per la tracciabilità.

Gli export di memoria conservano anche `phase`, `trial_id`, `response`, `target`, `correct`, `response_time_ms` e `displayed_client_ts`. La correttezza viene calcolata dal server. I tempi sono stime nel browser, non misure validate per esperimenti di timing preciso.

### Area ricercatore

Aprire l'app in un'altra scheda con `?researcher=1`. Configurare una password privata in **Settings → Secrets** su Streamlit Cloud:

```toml
researcher_password = "SOSTITUISCI_CON_UNA_PASSWORD_PRIVATA"
```

In locale si può usare `.streamlit/secrets.toml` (escluso da Git) oppure la variabile `INSTALAB_RESEARCHER_PASSWORD`, che ha precedenza. Non esiste una password predefinita; senza configurazione la sezione non legge il database. Non inserire password nell'indirizzo o nel repository.

Dopo l'accesso, **Aggiorna dati** legge le sessioni del server. I filtri consentono di scegliere partecipante, sessioni, fase e completamento. Sono disponibili:

- **Risposte OLD/NEW (CSV)**: una riga per risposta, con metadati dello stimolo e valutazione.
- **Registro like/dislike (CSV)**: reazioni e rimozioni.
- **Reazioni finali per volto (CSV)**: LIKE, DISLIKE o NONE per ogni volto su cui è stata espressa almeno una reazione.
- **Registro completo (CSV/JSON)**: tutti gli eventi filtrati; il JSON mantiene i metadati strutturati. I CSV proteggono i testi interpretabili come formule dai fogli di calcolo.
- **Metriche del feed (CSV)**: `feed_metrics.csv`, una riga per ciascuno dei 30 post assegnati, dopo la finalizzazione del feed, con tempi al 75%, reazioni e azioni social. Comprende gli zeri dei post mai sufficientemente visibili e segnala i tempi mancanti. Vedi [definizioni e limiti delle metriche](docs/feed_metrics.md).

L'anteprima della memoria mostra al massimo 500 righe, mentre i download includono tutte le righe filtrate. **Esci dall'area ricercatore** termina l'accesso per quella sessione del browser. Il parametro precedente `?preview=1` è un pannello di sviluppo della singola sessione, non sostituisce l'area ricercatore protetta.

### Eliminare sessioni di prova

Nell'area autenticata aprire **Elimina sessioni di prova**, selezionare gli ID desiderati e premere **Elimina le sessioni selezionate**. La conferma mostra sessioni ed eventi interessati e permette un backup JSON oppure l'annullamento. Per procedere occorre scrivere **ELIMINA** e premere **Elimina definitivamente**.

Viene eliminata l'intera sessione, comprese entrambe le fasi. Non esiste un ripristino nell'app e le copie già esportate restano esterne. L'operazione è atomica. Il database conserva ID e orario di cancellazione, senza risposte, per impedire a schede aperte o reinvii ritardati di ricreare la sessione. Una sessione eliminata viene fermata al successivo aggiornamento.

## Registrazione e conservazione

Gli eventi vengono salvati in `.local-data/events.sqlite3`, escluso da Git. `INSTALAB_DB_PATH` permette di scegliere un altro percorso sul server. I reinvii dello stesso evento non creano duplicati; le nuove sessioni hanno codici partecipante e sessione distinti. Un errore di scrittura viene segnalato con la possibilità di riprovare.

Il file SQLite rimane dopo un riavvio solo se il disco resta disponibile. Il disco effimero di Streamlit Community Cloud non garantisce la conservazione dopo ricreazioni o redeploy. Per una raccolta reale occorre configurare storage durevole e backup. Nessuna anonimizzazione, durata di conservazione o approvazione etica viene dichiarata come già configurata. Completare le informazioni nel consenso, le condizioni di utilizzo degli stimoli e la validazione del protocollo prima del reclutamento.

## Codice e controlli

- `app.py`: consenso, sessione, fasi e collegamento al componente.
- `stimulus_catalog.py`: lettura, validazione e selezione dal manifest.
- `validate_stimuli.py`: controllo del catalogo da terminale.
- `recognition.py`: piano OLD/NEW e valutazione delle risposte.
- `experiment_protocol.py`: quote e versione del protocollo condivise da selezione e riconoscimento.
- `event_store.py`, `export_data.py`, `research_dashboard.py`: salvataggio, export e gestione ricercatore.
- `feed.js`, `styles.css`: interfaccia e interazioni.
- `image_assets.py`: derivate WebP in memoria (qualità 92, lato massimo 960 px), orientamento EXIF e cache; originali invariati. Prima presentazione e OLD usano la stessa derivata.
- `feed_tracking.js`, `feed_metrics.py`: timer della Fase 1, gestione dei checkpoint e aggregazione delle metriche esportate.

Il browser riceve nel feed solo le 30 immagini selezionate e nel riconoscimento la prova attuale con precaricamento delle due successive. I NEW non vengono inviati nella prima fase. Le immagini decodificate vengono mantenute durante gli aggiornamenti. Un errore abilita **Riprova caricamento** e impedisce risposte su un'immagine non caricata.

Se un rerender interrompe la decodifica di un'immagine già caricata correttamente, il browser la ritenta automaticamente senza conservare una promessa rifiutata. I callback aggiornano la scheda corrente; gli errori effettivi continuano a mostrare **Riprova caricamento**.

```sh
python -m unittest discover -s tests
```

I controlli browser facoltativi richiedono Playwright e Chromium: `python tests/browser_continue.py`, `python tests/browser_images.py` e `python tests/browser_feed_metrics.py`. La variabile `CHROMIUM_PATH` può indicare un eseguibile diverso.

I vecchi contenuti dimostrativi, la configurazione JSON sostituita dal manifest, le anteprime statiche e i file di sistema macOS sono stati rimossi. Test automatici, immagini del nuovo catalogo e dati raccolti vengono conservati. Le rimozioni non cancellano la cronologia Git; per pubblicare le modifiche occorre un successivo commit e push esplicitamente richiesto.
