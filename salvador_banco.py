import socket
import json
import sqlite3
from datetime import datetime
import os
import time

# --- CONFIGURAÇÕES --- No salvador_banco.py
UDP_IP = "127.0.0.1"
UDP_PORT = 5008  
ARQUIVO_DB = "rastreamento_alvos.db"

ultimo_nome_visto = None
tempo_ultima_visao = 0  # <--- NOVA VARIÁVEL DE TEMPO

def inicializar_banco():
    conn = sqlite3.connect(ARQUIVO_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_deteccoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT,
            nome TEXT,
            centro_x INTEGER,
            centro_y INTEGER,
            distancia_cm REAL,
            reconhecido BOOLEAN
        )
    ''')
    conn.commit()
    return conn, cursor

conn, cursor = inicializar_banco()
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind((UDP_IP, UDP_PORT))

print("===========================================")
print(f" [BANCO DE DADOS] '{ARQUIVO_DB}' Pronto.")
print(f" [REDE] Aguardando Visão na porta {UDP_PORT}...")
print(" [FILTRO] Modo Anti-Spam (Biometria + Tempo) ativado.")
print("===========================================\n")

try:
    while True:
        dados_recebidos, endereco = sock.recvfrom(1024) 
        mensagem_str = dados_recebidos.decode('utf-8')
        dados = json.loads(mensagem_str)
        
        nome_atual = dados['nome']
        
        agora_dt = datetime.now()
        agora_str = agora_dt.strftime("%Y-%m-%d %H:%M:%S")
        tempo_atual_segundos = agora_dt.timestamp()
        
        # --- FILTRO AVANÇADO (BIOMETRIA + TEMPO) ---
        # Só ignora se for a mesma pessoa E se tiver passado menos de 5 minutos (300 segundos)
        # Se a pessoa sair e voltar depois de 5 minutos, o sistema regista a nova aparição!
        if nome_atual == ultimo_nome_visto:
            if (tempo_atual_segundos - tempo_ultima_visao) < 300:
                continue 
        
        ultimo_nome_visto = nome_atual
        tempo_ultima_visao = tempo_atual_segundos
        
        cursor.execute('''
            INSERT INTO historico_deteccoes 
            (data_hora, nome, centro_x, centro_y, distancia_cm, reconhecido)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            agora_str,
            dados['nome'],
            dados['centro_x'],
            dados['centro_y'],
            dados['distancia_cm'],
            dados['reconhecido']
        ))
        
        conn.commit()
        
        if dados["reconhecido"]:
            print(f"[{agora_str}] SALVO -> ALVO RECONHECIDO: {dados['nome']}")
        else:
            print(f"[{agora_str}] SALVO -> ROSTO DESCONHECIDO DETECTADO")

except KeyboardInterrupt:
    print("\n[INFO] Encerrando o salvamento no banco de dados...")
finally:
    conn.close()
    sock.close()
