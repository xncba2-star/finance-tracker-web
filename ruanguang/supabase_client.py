import streamlit as st
from supabase import create_client

def get_supabase(session=None):
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    client = create_client(url, key)
    if session:
        client.auth.set_session(session["access_token"], session["refresh_token"])
    return client

def sign_in(email, password):
    client = get_supabase()
    return client.auth.sign_in_with_password({"email": email, "password": password}).session

def sign_up(email, password):
    client = get_supabase()
    return client.auth.sign_up({"email": email, "password": password})

def get_auth_user(client):
    return client.auth.get_user().user

def sign_out(client):
    try:
        client.auth.sign_out()
    except Exception:
        pass
