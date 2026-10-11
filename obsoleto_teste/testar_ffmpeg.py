import os
import subprocess
import asyncio
import edge_tts
import winsound
import time
from colorama import init, Fore, Style

init()

# Lista com as vozes oficiais e gratuitas do Edge TTS para o Brasil
vozes_disponiveis = [
    "pt-BR-FranciscaNeural",  # Voz feminina
    "pt-BR-AntonioNeural"     # Voz masculina
]

async def gerar_e_tocar():
    print(Fore.CYAN + "=============================================")
    print("      TESTE DE VOZES (EDGE TTS - CLOUD)")
    print("=============================================\n" + Style.RESET_ALL)
    
    for voz in vozes_disponiveis:
        print(Fore.YELLOW + f"Gerando áudio para a voz: {voz}..." + Style.RESET_ALL)
        
        # Extrai o nome da voz
        nome = voz.split('-')[2].replace('Neural', '')
        texto = f"Olá, Rogério! Eu sou a {nome}. O que você acha do meu tom de voz para o seu robô?"
        
        comunicar = edge_tts.Communicate(texto, voz)
        await comunicar.save("teste_voz.mp3")
        
        # Converte via FFmpeg
        comando = [
            'ffmpeg', '-y', '-i', 'teste_voz.mp3',
            '-ar', '44100', '-ac', '1', '-sample_fmt', 's16', 'teste_voz.wav'
        ]
        
        subprocess.run(comando, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        print(Fore.GREEN + f"-> Reproduzindo a voz de {nome}...\n" + Style.RESET_ALL)
        winsound.PlaySound("teste_voz.wav", winsound.SND_FILENAME)
        
        time.sleep(1)

    try:
        os.remove("teste_voz.mp3")
        os.remove("teste_voz.wav")
    except:
        pass
        
    print(Fore.CYAN + "Teste concluído!" + Style.RESET_ALL)

if __name__ == "__main__":
    asyncio.run(gerar_e_tocar())
