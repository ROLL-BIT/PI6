import socket
import pyttsx3
import time
import wave
import audioop
import traceback
import os
from colorama import init, Fore, Style

init()

# ==============================================================================
# CONFIGURAÇÕES DE REDE
# ==============================================================================
UDP_IP = "127.0.0.1"
PORTA_ESCUTA = 5006  
PORTA_BOCA = 5007    
PORTA_MUTE = 5010    

# --- INTEGRAÇÃO ESP32 ---
ESP32_IP = "192.168.18.106"
ESP32_PORT = 5000

sock_escuta = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_escuta.bind((UDP_IP, PORTA_ESCUTA))

sock_aviso = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock_saida_audio = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# ==============================================================================
# CONFIGURAÇÃO DO MOTOR DE VOZ OFFLINE
# ==============================================================================
engine = pyttsx3.init()
engine.setProperty('rate', 170) 

voices = engine.getProperty('voices')
for voice in voices:
    if "brazil" in voice.name.lower() or "portuguese" in voice.name.lower():
        engine.setProperty('voice', voice.id)
        break

def avisar_status(mensagem):
    sock_aviso.sendto(mensagem.encode('utf-8'), (UDP_IP, PORTA_BOCA))
    sock_aviso.sendto(mensagem.encode('utf-8'), (UDP_IP, PORTA_MUTE))

# ==============================================================================
# LOOP PRINCIPAL
# ==============================================================================
print(Fore.CYAN + "=======================================================")
print("[SERVIDOR DE VOZ] Conectado ao alto-falante do ESP32.")
print("=======================================================" + Style.RESET_ALL)

while True:
    try:
        dados, _ = sock_escuta.recvfrom(4096)
        texto = dados.decode('utf-8')
        
        if texto:
            print(Fore.CYAN + f"\n[FALANDO]: {texto}" + Style.RESET_ALL)
            
            # 1. Avisa a arquitetura que vai falar e muta o microfone
            avisar_status("INICIOU_FALA")
            
            # 2. Grava a voz num ficheiro temporário para obtermos os PCM brutos
            arquivo_temp = "fala_temp.wav"
            engine.save_to_file(texto, arquivo_temp)
            engine.runAndWait()
            
            # 3. AQUECIMENTO DO ÁUDIO (Acorda o amplificador do ESP32)
            sock_saida_audio.sendto(b'\x00' * 1024, (ESP32_IP, ESP32_PORT))
            time.sleep(0.08)
            
            # 4. Extrai e converte a voz para 44.100Hz
            with wave.open(arquivo_temp, 'rb') as wf:
                framerate_original = wf.getframerate()
                audio_data = wf.readframes(wf.getnframes())
            
            estado_conversao = None
            if framerate_original != 44100:
                audio_44k, estado_conversao = audioop.ratecv(
                    audio_data, 2, 1, framerate_original, 44100, estado_conversao
                )
            else:
                audio_44k = audio_data
                
            # 5. SINCRONIZAÇÃO DE ALTA PRECISÃO VIA REDE
            CHUNK_ENVIO = 1024
            tempo_inicio = time.perf_counter()
            bytes_enviados = 0

            for i in range(0, len(audio_44k), CHUNK_ENVIO):
                pedaco = audio_44k[i:i+CHUNK_ENVIO]
                sock_saida_audio.sendto(pedaco, (ESP32_IP, ESP32_PORT))
                bytes_enviados += len(pedaco)

                tempo_ideal = bytes_enviados / (44100 * 2)  # 44100Hz * 2 bytes por amostra
                tempo_decorrido = time.perf_counter() - tempo_inicio
                tempo_espera = tempo_ideal - tempo_decorrido
                
                if tempo_espera > 0.001:
                    time.sleep(tempo_espera)

            # 6. Libera o microfone
            avisar_status("TERMINOU_FALA")
            
            # Limpeza do ficheiro
            try:
                os.remove(arquivo_temp)
            except:
                pass
            
    except Exception as e:
        print(Fore.RED + f"[ERRO NO SERVIDOR DE VOZ]: {e}" + Style.RESET_ALL)
        traceback.print_exc()
