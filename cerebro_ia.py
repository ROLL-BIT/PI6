# ==============================================================================
# 1. IMPORTAÇÕES E CONFIGURAÇÕES INICIAIS
# ==============================================================================
import time
import json
import socket
import sqlite3
import traceback
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

from agno.agent import Agent
from agno.tools import tool
from agno.models.groq import Groq

# ==============================================================================
# FORÇAR LEITURA CORRETA DO .ENV
# ==============================================================================
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
caminho_env = os.path.join(DIRETORIO_ATUAL, ".env")

load_dotenv(dotenv_path=caminho_env, override=True)

chave_groq = os.getenv("GROQ_API_KEY")
if not chave_groq:
    print("\n[ERRO FATAL] O arquivo .env não foi encontrado ou a variável GROQ_API_KEY está vazia!")

# ==============================================================================
# CONFIGURAÇÃO DE REDE E BANCO DE DADOS
# ==============================================================================
UDP_IP = "127.0.0.1"
PORTA_VOZ = 5006  
PORTA_ESCUTA_CEREBRO = 5011

sock_saida = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_entrada = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_entrada.bind((UDP_IP, PORTA_ESCUTA_CEREBRO))

base_dir = Path(__file__).parent.resolve()
dados_folder = base_dir / "dados"
dados_folder.mkdir(parents=True, exist_ok=True)

db_memoria_path = dados_folder / "memoria_robotica.db"
conn_memoria = sqlite3.connect(db_memoria_path, check_same_thread=False)
cursor_memoria = conn_memoria.cursor()

cursor_memoria.execute('''
    CREATE TABLE IF NOT EXISTS historico_conversas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data_hora TEXT,
        pergunta TEXT,
        resposta TEXT
    )
''')
conn_memoria.commit()

# ==============================================================================
# 2. FUNÇÕES AUXILIARES
# ==============================================================================
def enviar_para_fala(resposta: str):
    try:
        print(f"\n[IA RESPONDE]: {resposta}")
        sock_saida.sendto(resposta.encode('utf-8'), (UDP_IP, PORTA_VOZ))
    except Exception as e:
        print(f"[ERRO AO ENVIAR ÁUDIO]: {e}")

def entrada():
    try:
        dados, _ = sock_entrada.recvfrom(4096)
        pacote = json.loads(dados.decode('utf-8'))
        return pacote.get("texto", ""), pacote.get("nome", "Humano")
    except Exception:
        return None, None

# ==============================================================================
# 3. FERRAMENTAS DO AGENTE (APENAS MEMÓRIA DE CONVERSA)
# ==============================================================================
@tool
def buscar_conversas_antigas(assunto_ou_palavra_chave: str) -> str:
    """Use APENAS para buscar conversas ou frases faladas no passado."""
    try:
        query = f"%{assunto_ou_palavra_chave}%"
        cursor_memoria.execute(
            "SELECT data_hora, pergunta, resposta FROM historico_conversas WHERE pergunta LIKE ? OR resposta LIKE ? ORDER BY id DESC LIMIT 5", 
            (query, query)
        )
        resultados = cursor_memoria.fetchall()
        if not resultados: return "Nenhuma memória encontrada."
        return "Memórias:\n" + "\n".join([f"[{r[0]}] Humano disse: '{r[1]}' | Robô respondeu: '{r[2]}'" for r in resultados])
    except Exception as e:
        return f"Erro: {e}"

# As ferramentas de câmera foram desativadas temporariamente.

# ==============================================================================
# 4. CONFIGURAÇÃO DO AGENTE
# ==============================================================================
modelo = Groq(id="openai/gpt-oss-120b", api_key=chave_groq)

agent = Agent(
    name="Robo_IA",
    model=modelo,
    tools=[buscar_conversas_antigas], 
    instructions=[
        "Você é a Inteligência Artificial central de um robô avançado.",
        "Mantenha um tom de conversa natural e humano.",
        "AVISO DO SISTEMA: Seus sensores visuais (câmera) estão temporariamente DESATIVADOS para manutenção. Foque apenas na interação por voz.",
        "Trate a pessoa com quem está falando com respeito e responda de forma natural e amigável.",
        "REGRA 1: NUNCA escreva nomes de ferramentas no texto. Sua resposta deve conter APENAS o que o robô vai falar.",
        "Responda de forma curta e sem marcações markdown."
    ]
)

# ==============================================================================
# 5. LOOP PRINCIPAL DE EXECUÇÃO
# ==============================================================================
def IA0():
    print("=======================================================")
    print("[CÉREBRO IA] GPT OSS 120B Ativado. (Câmera OFF)")
    print("=======================================================")

    while True:
        comando, pessoa_atual = entrada()

        if comando:
            print(f"\n[{pessoa_atual} FALOU]: '{comando}'")
            data_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cursor_memoria.execute("SELECT pergunta, resposta FROM historico_conversas ORDER BY id DESC LIMIT 5")
            ultimas_conversas = cursor_memoria.fetchall()
            ultimas_conversas.reverse() 

            contexto_memoria = ""
            for conv in ultimas_conversas:
                contexto_memoria += f"Humano: {conv[0]}\nRobô: {conv[1]}\n\n"

            prompt_final = f"[MEMÓRIA RECENTE]\n{contexto_memoria}[DADOS ATUAIS] Data/Hora: {data_atual}\n\nHumano disse: '{comando}'\nSua resposta:"

            try:
                resposta_obj = agent.run(prompt_final)

                if resposta_obj and resposta_obj.content:
                    resposta_texto = str(resposta_obj.content).strip()
                    
                    if "tool_use_failed" in resposta_texto or "\"error\":" in resposta_texto or "{" in resposta_texto:
                        print(f"[BLOQUEADO PELO ESCUDO]: {resposta_texto}")
                        enviar_para_fala("Desculpe, a minha memória está fragmentada. Pode tentar perguntar de outra forma?")
                    else:
                        cursor_memoria.execute("INSERT INTO historico_conversas (data_hora, pergunta, resposta) VALUES (?, ?, ?)", (data_atual, comando, resposta_texto))
                        conn_memoria.commit()
                        enviar_para_fala(resposta_texto)
                else:
                    enviar_para_fala("Me perdi nos meus pensamentos.")
            
            except Exception as e:
                print(f"\n[ERRO CRÍTICO NO CÉREBRO]: {e}")
                traceback.print_exc()
                enviar_para_fala("Conexão neural perdida.")

if __name__ == "__main__":
    try:
        IA0()
    except KeyboardInterrupt:
        conn_memoria.close()
