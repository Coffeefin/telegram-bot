import os
from supabase import create_client

SUPABASE_URL = os.environ['SUPABASE_URL']
SUPABASE_KEY = os.environ['SUPABASE_KEY']
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ADMIN_ID = 1318872684

def execute_supabase_query(query):
    try:
        response = query.execute()
        return response.data if hasattr(response, 'data') else None
    except Exception as e:
        print(f"Supabase error: {e}")
        return None