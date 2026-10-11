import socket
import time
import wave
import traceback
import os
import json
import asyncio
import subprocess
import threading
import edge_tts
from colorama import init, Fore, Style
from pathlib import Path

init()

VOZ_ESCOLHIDA = "pt-BR-FranciscaNeural"
UDP_IP = "127.0.0.1"
PORTA_ESCUTA_TEXTO = 5006  
PORTA_BOCA = 5007    
PORTA_MUTE = 5010    
PORTA_PING_ESP = 5022 

# Garante que a pasta dados existe para guardar as infos do ESP32
base_dir = Path(__file__).parent.resolve()
dados_folder = base_dir / "dados"
dados_folder.mkdir(parents=True, exist_ok=True)
INFO_ESP32_PATH = dados_folder / "esp32_info.json"

esp32_endereco = None
sock_escuta = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_escuta.bind((UDP_IP, PORTA_ESCUTA_TEXTO))

sock_aviso = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

sock_telemetria = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_telemetria.bind(("0.0.0.0", PORTA_PING_ESP)) 

def escutar_ping_esp32():
    global esp32_endereco
    print(Fore.YELLOW + f"[REDE] A aguardar PING de telemetria do ESP32 na porta {PORTA_PING_ESP}..." + Style.RESET_ALL)
    
    while True:
        try:
            dados, endereco = sock_telemetria.recvfrom(1024)
            msg = dados.decode('utf-8', errors='ignore')
            
            if msg.startswith("PING_SPK"):
                if esp32_endereco != endereco:
                    esp32_endereco = endereco
                    partes = msg.split('|')
                    modelo = partes[1] if len(partes) > 1 else "Desconhecido"
                    mac = partes[2] if len(partes) > 2 else "Desconhecido"
                    
                    # Salva as informações para o Dashboard ler
                    info = {"ip": endereco[0], "porta": endereco[1], "modelo": modelo, "mac": mac, "ultima_conexao": time.time()}
                    try:
                        with open(INFO_ESP32_PATH, "w") as f:
                            json.dump(info, f)
                    except: pass

                    print(Fore.GREEN + f"\n[AUTO-DISCOVERY] Alto-falante ESP32 detetado!" + Style.RESET_ALL)
                    print(Fore.GREEN + f" -> IP: {endereco[0]} | Porta NAT: {endereco[1]} | Chip: {modelo} | MAC: {mac}" + Style.RESET_ALL)
        except Exception:
            pass

threading.Thread(target=escutar_ping_esp32, daemon=True).start()

def avisar_status(mensagem):
    sock_aviso.sendto(mensagem.encode('utf-8'), (UDP_IP, PORTA_BOCA))
    sock_aviso.sendto(mensagem.encode('utf-8'), (UDP_IP, PORTA_MUTE))

async def gerar_audio_nuvem(texto, arquivo_saida):
    communicate = edge_tts.Communicate(texto, VOZ_ESCOLHIDA)
    await communicate.save(arquivo_saida)

print(Fore.CYAN + "=======================================================")
print(f"[SERVIDOR DE VOZ] Edge TTS Cloud Ativado (Voz: {VOZ_ESCOLHIDA}).")
print("=======================================================" + Style.RESET_ALL)

while True:
    try:
        dados, _ = sock_escuta.recvfrom(4096)
        texto = dados.decode('utf-8')
        
        if texto:
            print(Fore.CYAN + f"\n[FALANDO via NUVEM]: {texto}" + Style.RESET_ALL)
            avisar_status("INICIOU_FALA")
            
            arquivo_mp3 = "fala_temp.mp3"
            arquivo_wav = "fala_temp.wav"
            
            asyncio.run(gerar_audio_nuvem(texto, arquivo_mp3))
            
            subprocess.run([
                'ffmpeg', '-y', 
                '-i', arquivo_mp3, 
                '-ar', '44100', 
                '-ac', '1', 
                '-sample_fmt', 's16', 
                arquivo_wav
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if esp32_endereco is None:
                print(Fore.RED + "[ERRO] Áudio descartado. O ESP32 ainda não enviou o seu IP de telemetria!" + Style.RESET_ALL)
                avisar_status("TERMINOU_FALA")
                continue

            sock_telemetria.sendto(b'\x00' * 1024, esp32_endereco)
            time.sleep(0.08)
            
            with wave.open(arquivo_wav, 'rb') as wf:
                audio_44k = wf.readframes(wf.getnframes())
                
            CHUNK_ENVIO = 1024
            tempo_inicio = time.perf_counter()
            bytes_enviados = 0

            for i in range(0, len(audio_44k), CHUNK_ENVIO):
                pedaco = audio_44k[i:i+CHUNK_ENVIO]
                sock_telemetria.sendto(pedaco, esp32_endereco) 
                bytes_enviados += len(pedaco)
                tempo_ideal = bytes_enviados / (44100 * 2) 
                tempo_decorrido = time.perf_counter() - tempo_inicio
                tempo_espera = tempo_ideal - tempo_decorrido
                if tempo_espera > 0.001:
                    time.sleep(tempo_espera)

            avisar_status("TERMINOU_FALA")
            
            try:
                os.remove(arquivo_mp3)
                os.remove(arquivo_wav)
            except: pass
            
    except Exception as e:
        print(Fore.RED + f"[ERRO NO SERVIDOR DE VOZ]: {e}" + Style.RESET_ALL)
        traceback.print_exc()
        avisar_status("TERMINOU_FALA")
