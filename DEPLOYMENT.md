# Guida al deploy su Firebase

Architettura: **Firebase Hosting** serve il frontend statico (`public/`) e inoltra le richieste `/api/**` a un servizio **Cloud Run** che esegue yt-dlp + ffmpeg in un container Docker (`backend/`).

## 0. Prerequisiti

- Un account Google con un progetto Firebase su piano **Blaze** (pay-as-you-go). Le rewrite di Hosting verso Cloud Run richiedono Blaze — è necessario anche solo per il piano gratuito di Cloud Run entro le soglie free tier.
- [Node.js](https://nodejs.org) (per Firebase CLI)
- [Google Cloud CLI](https://cloud.google.com/sdk/docs/install) (`gcloud`)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) in esecuzione (oppure puoi usare `gcloud run deploy --source` che builda da remoto con Cloud Build, senza Docker locale — consigliato, vedi step 4)

Installa la Firebase CLI se non l'hai già:

```bash
npm install -g firebase-tools
firebase login
```

## 1. Crea il progetto Firebase

Dalla [Firebase Console](https://console.firebase.google.com/) crea un nuovo progetto, oppure da CLI:

```bash
firebase projects:create ytconverter-tuonome
```

Poi passa al piano **Blaze** dalla console (Impostazioni progetto → Utilizzo e fatturazione).

Collega la cartella locale al progetto:

```bash
cd /Users/paoletoz/wa/ytconverter
firebase use --add
# seleziona il progetto appena creato, alias "default"
```

Aggiorna anche `.firebaserc` con l'ID reale del progetto (o lascia fare al comando sopra, che lo scrive automaticamente).

## 2. Configura gcloud

```bash
gcloud auth login
gcloud config set project ytconverter-tuonome
```

Abilita le API necessarie:

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
```

## 3. Scegli la region

Nel progetto ho usato `europe-west1` (Belgio) sia in `firebase.json` che nei comandi seguenti. Se vuoi un'altra region, sostituiscila ovunque compaia `europe-west1`.

## 4. Build & deploy del backend su Cloud Run

Dalla root del progetto:

```bash
cd backend
gcloud run deploy ytconverter-api \
  --source . \
  --region europe-west1 \
  --platform managed \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 540 \
  --concurrency 3 \
  --min-instances 0 \
  --max-instances 3
```

`--source .` fa buildare l'immagine da Cloud Build automaticamente (non serve Docker installato in locale). Il comando chiede conferma la prima volta per creare un repository Artifact Registry: accetta.

Al termine otterrai un URL tipo `https://ytconverter-api-xxxxx-ew.a.run.app`. Non serve usarlo direttamente: Firebase Hosting lo raggiungerà internamente tramite il nome del servizio (`ytconverter-api`) grazie al rewrite già configurato in `firebase.json`.

Nota su `--allow-unauthenticated`: rende il servizio raggiungibile pubblicamente (necessario perché Hosting possa fare da proxy). La protezione da abusi è affidata al rate-limit applicativo già incluso nel backend (15 download/ora e 30 info/ora per IP) — per un sito con più traffico valuta Firebase App Check o Cloud Armor (vedi sezione "Indurimento" più sotto).

## 5. Deploy del frontend (Firebase Hosting)

Torna alla root e deploya:

```bash
cd ..
firebase deploy --only hosting
```

Al termine la CLI stampa l'URL pubblico, tipo `https://ytconverter-tuonome.web.app`.

## 6. Verifica

Apri l'URL di Hosting, incolla un link YouTube e prova "Analizza" poi il download. Se qualcosa non va:

```bash
gcloud run services logs read ytconverter-api --region europe-west1 --limit 50
```

## 7. Redeploy dopo modifiche

- Solo frontend cambiato: `firebase deploy --only hosting`
- Solo backend cambiato: ripeti il comando `gcloud run deploy` dello step 4
- Entrambi: fai entrambi i comandi (l'ordine non è rilevante)

## Costi da monitorare

- **Cloud Run**: fatturato per CPU/memoria/tempo di esecuzione. Il download+conversione di un video può durare decine di secondi con CPU piena: imposta un budget alert.
- **Banda in uscita (egress)**: i file video/audio scaricati dagli utenti passano da Cloud Run verso Hosting/utente — con molti download di video lunghi i costi di banda possono crescere rapidamente.
- Imposta un **budget di fatturazione** in Google Cloud Console (Fatturazione → Budget e avvisi) per essere avvisato prima di spese impreviste.

## Indurimento consigliato (opzionale ma raccomandato se il sito è pubblico)

- **Firebase App Check** sul frontend, per verificare che le richieste a `/api/**` arrivino solo dalla tua pagina e non da script esterni.
- **Firebase Authentication** (anche solo login anonimo/Google) se vuoi limitare l'uso a utenti autenticati.
- **Cloud Armor** davanti a Cloud Run per limitare per IP/paese a livello di rete.
- Abbassa ulteriormente i limiti di rate-limit in `backend/main.py` (`@limiter.limit(...)`) se noti abusi.

## Nota legale

Questo strumento è pensato per uso personale (es. scaricare contenuti di cui detieni i diritti, o materiale con licenza che lo consente). Scaricare e ridistribuire contenuti protetti da copyright senza autorizzazione può violare i Termini di Servizio di YouTube e le leggi sul copyright applicabili. Evita di rendere il sito un servizio pubblico di massa senza controlli di accesso.
