"""
Monitor de Ambiente - Painel Streamlit
----------------------------------------
Busca os dados publicados pelo ESP32 no ThingSpeak e exibe
graficos de temperatura, umidade e nivel de ruido ao vivo.

Como rodar:
    pip install streamlit pandas requests streamlit-autorefresh
    streamlit run app.py

Depois é so preencher o Channel ID na barra lateral (ou deixar
o valor padrao ja preenchido) e o painel atualiza sozinho.
"""

import requests
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Monitor de Ambiente", page_icon="logo.png", layout="wide")


def check_password() -> bool:
    """Mostra uma tela de login simples antes de liberar o painel."""

    def password_entered():
        if st.session_state.get("password") == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.image("logo.png", use_container_width=True)
        st.text_input("Senha de acesso", type="password", on_change=password_entered, key="password")
        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("Senha incorreta.")
    return False


if not check_password():
    st.stop()

# ---------- Barra lateral: configuracoes ----------
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.image("logo.png", use_container_width=True)
with col_title:
    st.title("Monitor de Ambiente - ESP32")
    st.caption("Temperatura, umidade e nivel de ruido, atualizado ao vivo via ThingSpeak")

st.sidebar.image("logo.png", use_container_width=True)
st.sidebar.header("Configuracoes")
channel_id = st.sidebar.text_input("Channel ID do ThingSpeak", value="3422157")
read_api_key = st.sidebar.text_input(
    "Read API Key (deixe em branco se o canal for publico)", value="", type="password"
)
num_results = st.sidebar.slider("Quantidade de leituras exibidas", 10, 500, 100)
refresh_seconds = st.sidebar.slider("Atualizar a cada (segundos)", 5, 60, 20)

# Atualiza a pagina sozinha no intervalo escolhido
st_autorefresh(interval=refresh_seconds * 1000, key="auto_refresh")


@st.cache_data(ttl=5)
def fetch_data(channel_id: str, api_key: str, results: int) -> pd.DataFrame:
    url = f"https://api.thingspeak.com/channels/{channel_id}/feeds.json"
    params = {"results": results}
    if api_key:
        params["api_key"] = api_key

    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    feeds = data.get("feeds", [])
    if not feeds:
        return pd.DataFrame()

    df = pd.DataFrame(feeds)
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.rename(columns={
        "field1": "Temperatura",
        "field2": "Umidade",
        "field3": "Ruido_RMS",
        "field4": "Ruido_dB",
    })
    for col in ["Temperatura", "Umidade", "Ruido_RMS", "Ruido_dB"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.set_index("created_at")


try:
    df = fetch_data(channel_id, read_api_key, num_results)
except Exception as e:
    st.error(f"Nao foi possivel buscar os dados do ThingSpeak: {e}")
    st.stop()

if df.empty:
    st.warning("Nenhum dado encontrado ainda. Verifique o Channel ID ou espere o ESP32 enviar leituras.")
    st.stop()

# ---------- Cards com os valores mais recentes ----------
latest = df.iloc[-1]
col1, col2, col3 = st.columns(3)
col1.metric("Temperatura", f"{latest['Temperatura']:.1f} C" if pd.notna(latest['Temperatura']) else "--")
col2.metric("Umidade", f"{latest['Umidade']:.1f} %" if pd.notna(latest['Umidade']) else "--")
if "Ruido_dB" in df.columns and pd.notna(latest.get("Ruido_dB")):
    col3.metric("Nivel de ruido", f"{latest['Ruido_dB']:.1f} dB")
else:
    col3.metric("Nivel de ruido (RMS)", f"{latest['Ruido_RMS']:.0f}" if pd.notna(latest['Ruido_RMS']) else "--")

st.caption(f"Ultima leitura: {latest.name.strftime('%d/%m/%Y %H:%M:%S')}")

# ---------- Graficos ----------
st.subheader("Temperatura (C)")
st.line_chart(df[["Temperatura"]])

st.subheader("Umidade (%)")
st.line_chart(df[["Umidade"]])

if "Ruido_dB" in df.columns and df["Ruido_dB"].notna().any():
    st.subheader("Nivel de ruido (dB)")
    st.line_chart(df[["Ruido_dB"]])

if "Ruido_RMS" in df.columns and df["Ruido_RMS"].notna().any():
    with st.expander("Ver nivel de ruido em RMS bruto (historico anterior a calibracao em dB)"):
        st.line_chart(df[["Ruido_RMS"]])

with st.expander("Ver dados brutos"):
    st.dataframe(df)
