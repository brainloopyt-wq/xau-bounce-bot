# Bounce Bot V2 — Gemini selettivo, segnali Telegram e Supabase

## Installazione
Sostituire i file Python e requirements.txt nel repository GitHub. Render: build `pip install -r requirements.txt`, start `python main.py`. Le credenziali restano nelle variabili Environment di Render: `TWELVEDATA_API_KEY`, `SUPABASE_URL`, `SUPABASE_KEY`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

## Regole AI
- **A** (score tecnico >= 0.85): Telegram **AI NON CONSULTATA**, zero chiamate Gemini.
- **B** (0.65 <= score < 0.85): una richiesta Gemini; se approva, Telegram **VALIDATO DA GEMINI**; se respinge, niente notifica.
- **B con Gemini indisponibile / quota interna esaurita**: Telegram **AI NON DISPONIBILE — segnale tecnico NON validato**. NON significa approvazione AI.
- **C** (score < 0.65): nessuna notifica e nessuna chiamata Gemini.

Soglie configurabili con `V2_SCORE_A` (default `0.85`) e `V2_SCORE_B` (default `0.65`), `V2_GEMINI_DAILY_LIMIT` (default `10`). Sono score euristici, NON probabilita di successo. Il limite Gemini e in memoria e riparte da zero al riavvio di Render: non e una quota rigida tra riavvii. Nessuna richiesta Gemini se non c'e setup B. Non esiste deduplica persistente: riavvii possono duplicare un avviso.

## Compatibilita e limiti
- Il bot invia **solo notifiche**: nessun ordine automatico su XTB demo o reale.
- M15 ricavato da M5; 1 richiesta Twelve Data ogni 5 minuti, 300 candele richieste. Verificare i limiti del proprio piano Twelve Data.
- UptimeRobot HEAD supportato, ma HTTP 200 non certifica che il feed sia aggiornato e Render Free non garantisce uptime.
- Supabase usa le tabelle esistenti: `bot_status` id=1, `bounce_signals`. `tp_price` contiene TP2; TP1 solo nel messaggio Telegram. Per compatibilita con lo schema V1, `status=APPROVED` significa *segnale tecnico selezionato per invio*, non necessariamente validato da AI; leggere sempre `ai_reason` per lo stato AI. `ai_score` contiene lo score tecnico, non la confidenza AI.
- Se il salvataggio del segnale fallisce, il bot tenta comunque l'invio Telegram e registra l'errore nei Logs.
- Trailing stop **non monitorato automaticamente**; TP1/TP2 sono livelli indicativi. Non c'e conferma di esecuzione o monitoraggio delle posizioni XTB.
- Rischio 15 EUR NON verificato: dipende da lotto minimo, spread, contratto, cambio e slippage. Solo test demo, nessun rendimento o 80% garantito.
- Evitare due bot attivi sullo stesso Supabase / Telegram.

## Test Telegram
Per inviare un test all'avvio, impostare temporaneamente `V2_TEST_TELEGRAM_ON_START=true`, effettuare deploy e poi riportarlo a `false` per evitare messaggi ad ogni riavvio. Non pubblicare token nel repository.
