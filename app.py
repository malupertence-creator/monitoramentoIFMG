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

comparar = st.sidebar.checkbox("Comparar duas montagens (Sala A vs Sala B)", value=True)

st.sidebar.subheader("Sala A")
channel_id_a = st.sidebar.text_input("Channel ID - Sala A", value="3422157")
read_api_key_a = st.sidebar.text_input(
    "Read API Key - Sala A (em branco se publico)", value="", type="password", key="key_a"
)

channel_id_b = ""
read_api_key_b = ""
if comparar:
    st.sidebar.subheader("Sala B")
    channel_id_b = st.sidebar.text_input("Channel ID - Sala B", value="3426255")
    read_api_key_b = st.sidebar.text_input(
        "Read API Key - Sala B (em branco se publico)", value="", type="password", key="key_b"
    )

st.sidebar.divider()
modo = st.sidebar.radio("Periodo a visualizar", ["Ultimas leituras", "Um dia especifico"])

if modo == "Ultimas leituras":
    num_results = st.sidebar.slider("Quantidade de leituras exibidas", 10, 8000, 100)
    data_escolhida = None
else:
    num_results = 8000  # maximo permitido por requisicao no ThingSpeak
    data_escolhida = st.sidebar.date_input("Escolha o dia")

refresh_seconds = st.sidebar.slider("Atualizar a cada (segundos)", 5, 60, 20)

# Atualiza a pagina sozinha no intervalo escolhido
st_autorefresh(interval=refresh_seconds * 1000, key="auto_refresh")


@st.cache_data(ttl=5)
def fetch_data(channel_id: str, api_key: str, results: int, start=None, end=None) -> pd.DataFrame:
    url = f"https://api.thingspeak.com/channels/{channel_id}/feeds.json"
    params = {"results": results}
    if api_key:
        params["api_key"] = api_key
    if start is not None:
        params["start"] = start
    if end is not None:
        params["end"] = end

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


def buscar(channel_id, api_key):
    if data_escolhida is not None:
        start_str = data_escolhida.strftime("%Y-%m-%d") + " 00:00:00"
        end_str = data_escolhida.strftime("%Y-%m-%d") + " 23:59:59"
        return fetch_data(channel_id, api_key, num_results, start=start_str, end=end_str)
    return fetch_data(channel_id, api_key, num_results)


try:
    df_a = buscar(channel_id_a, read_api_key_a)
except Exception as e:
    st.error(f"Nao foi possivel buscar os dados da Sala A: {e}")
    st.stop()

df_b = pd.DataFrame()
if comparar:
    if not channel_id_b:
        st.warning("Preencha o Channel ID da Sala B na barra lateral para comparar.")
    else:
        try:
            df_b = buscar(channel_id_b, read_api_key_b)
        except Exception as e:
            st.error(f"Nao foi possivel buscar os dados da Sala B: {e}")

if df_a.empty:
    st.warning("Nenhum dado encontrado ainda para a Sala A. Verifique o Channel ID ou espere o ESP32 enviar leituras.")
    st.stop()

# ---------- Cards com os valores mais recentes ----------
latest_a = df_a.iloc[-1]
latest_b = df_b.iloc[-1] if not df_b.empty else None

st.subheader("Sala A")
col1, col2, col3 = st.columns(3)
col1.metric("Temperatura", f"{latest_a['Temperatura']:.1f} C" if pd.notna(latest_a['Temperatura']) else "--")
col2.metric("Umidade", f"{latest_a['Umidade']:.1f} %" if pd.notna(latest_a['Umidade']) else "--")
col3.metric("Nivel de ruido", f"{latest_a['Ruido_dB']:.1f} dB" if pd.notna(latest_a.get('Ruido_dB')) else "--")
st.caption(f"Ultima leitura Sala A: {latest_a.name.strftime('%d/%m/%Y %H:%M:%S')}")

if latest_b is not None:
    st.subheader("Sala B")
    col4, col5, col6 = st.columns(3)
    col4.metric("Temperatura", f"{latest_b['Temperatura']:.1f} C" if pd.notna(latest_b['Temperatura']) else "--")
    col5.metric("Umidade", f"{latest_b['Umidade']:.1f} %" if pd.notna(latest_b['Umidade']) else "--")
    col6.metric("Nivel de ruido", f"{latest_b['Ruido_dB']:.1f} dB" if pd.notna(latest_b.get('Ruido_dB')) else "--")
    st.caption(f"Ultima leitura Sala B: {latest_b.name.strftime('%d/%m/%Y %H:%M:%S')}")

# ---------- Cores fixas por sala ----------
COR_SALA_A = "#3B82F6"  # azul
COR_SALA_B = "#EF4444"  # vermelho

# ---------- Graficos por parametro ----------
def graficos_parametro(titulo, coluna):
    st.subheader(titulo)

    if latest_b is not None and coluna in df_b.columns:
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.caption("Sala A")
            st.line_chart(df_a[[coluna]].rename(columns={coluna: "Sala A"}), color=[COR_SALA_A])
        with col_b:
            st.caption("Sala B")
            st.line_chart(df_b[[coluna]].rename(columns={coluna: "Sala B"}), color=[COR_SALA_B])
        with col_c:
            st.caption("Comparacao")
            serie_a = df_a[coluna].resample("1min").mean() if coluna in df_a.columns else pd.Series(dtype=float)
            serie_b = df_b[coluna].resample("1min").mean()
            comp = pd.DataFrame({"Sala A": serie_a, "Sala B": serie_b})
            st.line_chart(comp, color=[COR_SALA_A, COR_SALA_B])
    else:
        # So uma montagem disponivel - mostra grafico unico, sem erro
        st.line_chart(df_a[[coluna]].rename(columns={coluna: "Sala A"}), color=[COR_SALA_A])


graficos_parametro("Temperatura (C)", "Temperatura")
graficos_parametro("Umidade (%)", "Umidade")
graficos_parametro("Nivel de ruido (dB)", "Ruido_dB")

with st.expander("Ver dados brutos - Sala A"):
    st.dataframe(df_a)
if latest_b is not None:
    with st.expander("Ver dados brutos - Sala B"):
        st.dataframe(df_b)
