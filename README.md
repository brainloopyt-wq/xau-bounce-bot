# Bounce Bot - alert soltanto (nessun ordine automatico)

Questa versione usa **Twelve Data XAU/USD M5**, NON l'API XTB (dismessa) e NON garantisce prezzi identici a XTB. Verificare che il proprio piano Twelve Data supporti XAU/USD e la frequenza richiesta; in caso contrario il bot segnala l'errore e non inventa prezzi.

## Render
- Tipo: Web Service, start command `python main.py`, Python 3.11+.
- Environment: `SUPABASE_URL`, `SUPABASE_KEY`, `TWELVEDATA_API_KEY`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- `SCAN_INTERVAL=300` opzionale; il programma impone comunque un intervallo minimo di 300 secondi. La disponibilità dei crediti dipende dal costo effettivo dell’endpoint e dal piano.
- Ruotare tutte le chiavi e password precedentemente esposte; non inserirle nei file.
- Supabase: creare la riga `bot_status` con `id=1` e verificare che RLS autorizzi SELECT/UPDATE per la chiave utilizzata. La tabella deve contenere `id`, `symbol`, `last_price`, `rsi`, `local_score`, `status_message`, `updated_at`. La tabella `bounce_signals` deve avere le colonne indicate in `main.py` e policy INSERT.
- Il feed può non fornire volume reale: senza volume il bonus volume di 0.3 non scatta; lo score massimo diventa 0.7, e la validazione Gemini è necessaria per i segnali che superano la soglia 0.5. La strategia originale è preservata e perciò lo score 0 è normale in assenza di setup.
- I segnali sono indicativi e non aprono operazioni. La deduplicazione degli alert è solo in memoria: un riavvio può ripetere un alert per la stessa candela. Per uso continuativo implementare una chiave univoca persistente per candela/segnale.
- Il server HTTP risponde 200 anche quando il feed è in errore: controllare i log e `bot_status.status_message`.

## Primo avvio
1. Impostare le variabili Environment su Render, senza pubblicare le chiavi.
2. Caricare i file nella radice del repository GitHub; comando di avvio `python main.py`.
3. Verificare che `bot_status` contenga la riga `id=1` e che RLS permetta di aggiornarla.
4. Controllare Logs: `Candle=...`, `price=...`, `RSI=...` e assenza di errori.
5. Controllare in Supabase `updated_at`, `last_price`, `rsi` e `status_message`. `local_score=0` è normale senza setup.
6. Non utilizzare segnali per operazioni reali prima di backtest e verifica indipendente.
