from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_bounce_signal(signal_data: dict):
    """
    Salva il segnale di rimbalzo nella tabella dedicata 'bounce_signals' su Supabase.
    """
    try:
        response = supabase.table("bounce_signals").insert(signal_data).execute()
        return response
    except Exception as e:
        print(f"[ERROR DB] Errore nel salvataggio su Supabase: {e}")
        return None