import os
import wave
import time
import numpy as np
import io
import socket
import json
import threading
import traceback
from groq import Groq
from dotenv import load_dotenv

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
caminho_env = os.path.join(DIRETORIO_ATUAL, ".env")
load_dotenv(dotenv_path=caminho_env, override=True)

chave_groq = os.getenv("GROQ_API_KEY")
if not chave_groq:
    print("\n[ERRO FATAL] O ficheiro .env não foi encontrado ou a GROQ_API_KEY está vazia!")

client = Groq(api_key=chave_groq)

UDP_IP = "127.0.0.1"
UDP_PORT_CEREBRO = 5011     
UDP_PORT_STATUS_FALA = 5010 
PORTA_MIC_ESP32 = 5000 
GANHO_MICROFONE = 4.0  

pessoa_na_camera = "Humano"
robo_falando = False

sock_envio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_esp32 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_esp32.bind(("0.0.0.0", PORTA_MIC_ESP32))

def udp_thread_status_fala():
    global robo_falando
    sock_fala = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_fala.bind((UDP_IP, UDP_PORT_STATUS_FALA))
    print(f"[REDE] A ouvir status da voz na porta {UDP_PORT_STATUS_FALA}...")
    while True:
        try:
            dados, _ = sock_fala.recvfrom(1024)
            status = dados.decode('utf-8')
            if "INICIOU_FALA" in status:
                robo_falando = True
                print("\n[AUDIO] Robô a falar. Microfone do ESP32 IGNORADO.")
            elif "TERMINOU_FALA" in status:
                robo_falando = False
                print("\n[AUDIO] Robô em silêncio. Microfone REATIVADO.")
        except Exception:
            pass

threading.Thread(target=udp_thread_status_fala, daemon=True).start()

# === SUBSTITUTO MATEMÁTICO PARA O AUDIOOP ===
def processar_audio(dados_brutos, ganho):
    arr = np.frombuffer(dados_brutos, dtype=np.int16)
    arr = np.clip(arr * ganho, -32768, 32767).astype(np.int16)
    return arr.tobytes(), np.max(arr)

RATE = 16000     
CHUNK = 512      
SILENCE_TIMEOUT = 0.8  

print("\n[SISTEMA] A calcular ruído de fundo do ESP32 (Fique em silêncio por 2.5s)...")
frames_ruido = []

timeout_start = time.time()
while time.time() - timeout_start < 2.5: 
    try:
        sock_esp32.settimeout(0.5)
        dados, endereco = sock_esp32.recvfrom(2048)
        
        if len(dados) < 64: 
            continue
        
        _, volume_atual = processar_audio(dados, GANHO_MICROFONE)
        frames_ruido.append(volume_atual)
    except socket.timeout:
        pass
    except Exception:
        pass

sock_esp32.settimeout(None)
THRESHOLD = int(np.mean(frames_ruido) * 1.5) if frames_ruido else 2000
print(f"[SISTEMA] Limite de som ajustado para: {THRESHOLD}")

def transcrever_e_enviar(frames, alvo_atual):
    start_time = time.time()
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2) 
        wf.setframerate(RATE)
        wf.writeframes(b"".join(frames))
    wav_io.name = "temp_audio.wav"
    wav_io.seek(0)
    
    try:
        transcription = client.audio.transcriptions.create(
            file=(wav_io.name, wav_io.read()),
            model="whisper-large-v3",
            language="pt",
            response_format="json",
            temperature=0.0,
        )
        texto = transcription.text.strip()
        elapsed = time.time() - start_time
        if texto:
            print(f"\n[VOCÊ ({elapsed:.1f}s)]: {texto}")
            pacote = json.dumps({"texto": texto, "nome": alvo_atual})
            sock_envio.sendto(pacote.encode('utf-8'), (UDP_IP, UDP_PORT_CEREBRO))
    except Exception as e:
        print(f"\n[ERRO CRÍTICO NA TRANSCRIÇÃO]: {e}")
        traceback.print_exc()

print("\n=======================================================")
print(f"[MIC] MODO NUVEM: Escuta ativa na porta {PORTA_MIC_ESP32}...")
print("=======================================================\n")

try:
    while True:
        dados, endereco = sock_esp32.recvfrom(2048)
        
        if len(dados) < 64: 
            continue
        
        pcm, volume_atual = processar_audio(dados, GANHO_MICROFONE)

        if volume_atual > THRESHOLD and not robo_falando:
            alvo_atual = pessoa_na_camera
            frames = [pcm]
            silent_frames = 0
            
            print(f"\r[!] Captando áudio vindo de {endereco[0]}...  ", end="", flush=True)

            while True:
                dados, _ = sock_esp32.recvfrom(2048)
                if len(dados) < 64: continue
                
                pcm, volume_loop = processar_audio(dados, GANHO_MICROFONE)
                frames.append(pcm)

                if volume_loop < THRESHOLD:
                    silent_frames += 1
                    
                    if silent_frames > (SILENCE_TIMEOUT * RATE / 512):
                        duracao_seg = (len(frames) * CHUNK) / RATE
                        if duracao_seg > (SILENCE_TIMEOUT + 0.1): 
                            threading.Thread(target=transcrever_e_enviar, args=(frames, alvo_atual)).start()
                        
                        sock_esp32.setblocking(False)
                        try:
                            while True: sock_esp32.recvfrom(2048)
                        except Exception:
                            pass
                        sock_esp32.setblocking(True)
                        break
                else:
                    silent_frames = 0

except KeyboardInterrupt:
    print("\n[INFO] A encerrar o sistema de áudio...")
finally:
    sock_esp32.close()
