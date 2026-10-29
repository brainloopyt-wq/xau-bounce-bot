from datetime import datetime, timezone
from supabase import create_client
from config import SUPABASE_URL, SUPABASE_KEY, SYMBOL

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError('Configura SUPABASE_URL e SUPABASE_KEY su Render')
client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_bot_status(*, price=None, rsi=None, local_score=None, message='Attivo'):
    fields = {'symbol': SYMBOL, 'status_message': message,
              'updated_at': datetime.now(timezone.utc).isoformat()}
    for key, value in [('last_price', price), ('rsi', rsi), ('local_score', local_score)]:
        if value is not None:
            fields[key] = float(value)
    # UPDATE does not erase old values if the feed fails.
    result = client.table('bot_status').update(fields).eq('id', 1).execute()
    if not result.data:
        raise RuntimeError('bot_status id=1 non aggiornata: crea la riga e verifica RLS')
    return result.data

def save_bounce_signal(signal_data: dict):
    result = client.table('bounce_signals').insert(signal_data).execute()
    if not result.data:
        raise RuntimeError('Inserimento bounce_signals non confermato')
    return result.data
