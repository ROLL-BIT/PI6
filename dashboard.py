import streamlit as st
import sqlite3
import pandas as pd
import json
import os
from datetime import datetime
from pathlib import Path

# Configuração da página: Modo Amplo e Título
st.set_page_config(page_title="SAGA-IoT Dashboard", page_icon="🤖", layout="wide")

# CSS Minimalista e Dark Mode Refinado
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; }
    h1, h2, h3, p { font-family: 'Inter', sans-serif; }
    .metric-box {
        background-color: #262730;
        border-radius: 8px;
        padding: 15px;
        text-align: center;
        border: 1px solid #333;
    }
    .metric-title { font-size: 14px; color: #888; margin-bottom: 5px; }
    .metric-value { font-size: 28px; font-weight: bold; color: #00FFCC; }
    </style>
""", unsafe_allow_html=True)

st.title("🤖 Cérebro SAGA-IoT")
st.markdown("Monitoramento de IA em Nuvem e Telemetria de Hardware")

# ==========================================================
# 1. CARREGAMENTO DOS DADOS DO ESP32 (Via JSON)
# ==========================================================
base_dir = Path(__file__).parent.resolve()
dados_folder = base_dir / "dados"
INFO_ESP32_PATH = dados_folder / "esp32_info.json"

ip_esp = "Desconectado"
modelo_esp = "Nenhum"
mac_esp = "N/A"

if INFO_ESP32_PATH.exists():
    try:
        with open(INFO_ESP32_PATH, "r") as f:
            info = json.load(f)
            ip_esp = info.get("ip", "Desconectado")
            modelo_esp = info.get("modelo", "Nenhum")
            mac_esp = info.get("mac", "N/A")
    except: pass

# ==========================================================
# 2. CARREGAMENTO DO BANCO DE DADOS (Tokens e Nomes)
# ==========================================================
db_path = dados_folder / "memoria_robotica.db"

@st.cache_data(ttl=5) # Atualiza a cada 5 segundos automaticamente
def load_data():
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    # Traz apenas as conversas que já têm tokens (após atualização)
    df = pd.read_sql_query("SELECT * FROM historico_conversas WHERE tokens_estimados IS NOT NULL", conn)
    conn.close()
    if not df.empty:
        df['data_hora'] = pd.to_datetime(df['data_hora'])
        df['data_apenas'] = df['data_hora'].dt.date
    return df

df = load_data()

# Processamento se existirem dados
if not df.empty:
    hoje = datetime.now().date()
    df_hoje = df[df['data_apenas'] == hoje]
    
    tokens_hoje = int(df_hoje['tokens_estimados'].sum())
    tokens_total = int(df['tokens_estimados'].sum())
    pessoas_faladas = df_hoje['nome_pessoa'].dropna().unique()
else:
    tokens_hoje = 0
    tokens_total = 0
    pessoas_faladas = []

# ==========================================================
# 3. INTERFACE DE MÉTRICAS SUPERIORES
# ==========================================================
st.markdown("### 📊 Status de Conexão e API")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"<div class='metric-box'><div class='metric-title'>Chip ESP32 Atual</div><div class='metric-value'>{modelo_esp}</div></div>", unsafe_allow_html=True)
with col2:
    st.markdown(f"<div class='metric-box'><div class='metric-title'>IP do Chassi (Borda)</div><div class='metric-value'>{ip_esp}</div></div>", unsafe_allow_html=True)
with col3:
    st.markdown(f"<div class='metric-box'><div class='metric-title'>Tokens LLM (Hoje)</div><div class='metric-value'>{tokens_hoje}</div></div>", unsafe_allow_html=True)
with col4:
    st.markdown(f"<div class='metric-box'><div class='metric-title'>Tokens LLM (Total)</div><div class='metric-value'>{tokens_total}</div></div>", unsafe_allow_html=True)

st.divider()

# ==========================================================
# 4. GRÁFICOS E LISTAS
# ==========================================================
col_grafico, col_lista = st.columns([2, 1])

with col_grafico:
    st.markdown("### 📈 Consumo de Tokens por Dia")
    if not df.empty:
        grafico_dados = df.groupby('data_apenas')['tokens_estimados'].sum().reset_index()
        grafico_dados.set_index('data_apenas', inplace=True)
        st.bar_chart(grafico_dados, color="#00FFCC")
    else:
        st.info("Aguardando o robô conversar para gerar o gráfico...")

with col_lista:
    st.markdown("### 🗣️ Interações de Hoje")
    if len(pessoas_faladas) > 0:
        for pessoa in pessoas_faladas:
            if pessoa.strip():
                st.markdown(f"- **{pessoa}**")
    else:
        st.write("O robô ainda não falou com ninguém hoje.")

# ==========================================================
# 5. TABELA DE MEMÓRIA BRUTA
# ==========================================================
st.markdown("### 🧠 Registro Ocular (Últimas 10 falas)")
if not df.empty:
    df_tabela = df.sort_values(by="id", ascending=False).head(10)
    df_tabela = df_tabela[["data_hora", "nome_pessoa", "pergunta", "resposta", "tokens_estimados"]]
    df_tabela.columns = ["Data e Hora", "Pessoa", "Humano Falou", "Robô Respondeu", "Tokens"]
    st.dataframe(df_tabela, use_container_width=True, hide_index=True)
