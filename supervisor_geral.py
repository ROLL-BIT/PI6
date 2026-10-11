import subprocess
import threading
import time
import psutil
import os
from colorama import init, Fore, Style

init()

TIMEOUT = 20

# Agora o dashboard faz parte da lista!
PROCESSOS_SILENCIOSOS = [
    "ponte_interface",  
    "servidor_fala", 
    "gravador_inteligente", 
    "cerebro_ia",
    "dashboard"
]

CORES = {
    "ponte_interface": Fore.YELLOW, 
    "servidor_fala": Fore.CYAN,
    "gravador_inteligente": Fore.MAGENTA,
    "cerebro_ia": Fore.LIGHTGREEN_EX,
    "dashboard": Fore.BLUE
}

processos = {}
ultimo_print = {}

def som_caiu(): print(Fore.RED + Style.BRIGHT + "\n[!!!] ALERTA: UM MÓDULO CAIU [!!!]\n" + Style.RESET_ALL)
def som_travou(): print(Fore.RED + Style.BRIGHT + "\n[!!!] ALERTA: MÓDULO TRAVOU [!!!]\n" + Style.RESET_ALL)
def som_inicio(): print(Fore.GREEN + "\n[ OK ] Sistema de monitoramento iniciado (Modo Nuvem)...\n" + Style.RESET_ALL)

def iniciar(nome, arquivo):
    comando_python = "python3" if os.name != "nt" else "python"
    
    print(Fore.WHITE + Style.BRIGHT + f">>> Iniciando Módulo: {nome} ({arquivo})..." + Style.RESET_ALL)
    
    # A Mágica: Se for o dashboard, roda via Streamlit!
    if nome == "dashboard":
        comando = [comando_python, "-m", "streamlit", "run", arquivo, "--server.port=80", "--server.address=0.0.0.0", "--server.headless=true"]
    else:
        comando = [comando_python, "-u", arquivo]
        
    p = subprocess.Popen(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    processos[nome] = p
    ultimo_print[nome] = time.time()
    t = threading.Thread(target=ler_saida, args=(nome,))
    t.daemon = True
    t.start()

def ler_saida(nome):
    p = processos[nome]
    if p.stdout:
        for linha in p.stdout:
            ultimo_print[nome] = time.time()
            cor = CORES.get(nome, Fore.WHITE)
            print(cor + f"[{nome}] " + linha.strip() + Style.RESET_ALL)

def monitorar():
    tempo_ultimo_status = time.time()
    while True:
        agora = time.time()
        mostrar_recursos = (agora - tempo_ultimo_status) >= 10 
        
        if mostrar_recursos:
            print(Fore.YELLOW + "\n--- CONSUMO DE HARDWARE DA VPS (CPU / RAM) ---" + Style.RESET_ALL)

        for nome, p in list(processos.items()):
            if p.poll() is not None:
                print(Fore.RED + Style.BRIGHT + f"[{nome}] CAIU! Reiniciando o módulo..." + Style.RESET_ALL)
                som_caiu()
                arquivo_alvo = f"{nome}.py"
                iniciar(nome, arquivo_alvo)
                continue

            if nome not in PROCESSOS_SILENCIOSOS and (agora - ultimo_print[nome] > TIMEOUT):
                print(Fore.RED + Style.BRIGHT + f"[{nome}] TRAVOU por {TIMEOUT}s. Forçando reinício..." + Style.RESET_ALL)
                som_travou()
                p.kill()
                arquivo_alvo = f"{nome}.py"
                iniciar(nome, arquivo_alvo)
                continue

            if mostrar_recursos:
                try:
                    proc = psutil.Process(p.pid)
                    mem_mb = proc.memory_info().rss / (1024 * 1024)
                    cpu_perc = proc.cpu_percent(interval=None) 
                    cor_status = Fore.WHITE
                    if cpu_perc > 50.0 or mem_mb > 300.0: cor_status = Fore.RED 
                    print(cor_status + f" -> {nome.upper().ljust(21)} | CPU: {cpu_perc:>4.1f}% | RAM: {mem_mb:>5.1f} MB" + Style.RESET_ALL)
                except: pass
        
        if mostrar_recursos:
            print(Fore.YELLOW + "---------------------------------------\n" + Style.RESET_ALL)
            tempo_ultimo_status = agora
        time.sleep(2) 

def encerrar_tudo():
    print(Fore.RED + Style.BRIGHT + "\n[SUPERVISOR] A desligar todos os módulos em segurança..." + Style.RESET_ALL)
    for nome, p in processos.items():
        if p.poll() is None:
            try:
                p.terminate() 
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill() 
            except Exception: pass
    print(Fore.GREEN + Style.BRIGHT + "[SUPERVISOR] Sistema finalizado. Portas libertadas.\n" + Style.RESET_ALL)

if __name__ == '__main__':
    print(Fore.GREEN + Style.BRIGHT + "=======================================")
    print("  SUPERVISOR GERAL INICIADO (VPS READY)")
    print("=======================================" + Style.RESET_ALL)
    som_inicio()

    iniciar("ponte_interface", "ponte_interface.py") 
    iniciar("servidor_fala", "servidor_fala.py")   
    iniciar("gravador_inteligente", "gravador_inteligente.py")
    iniciar("cerebro_ia", "cerebro_ia.py") 
    iniciar("dashboard", "dashboard.py") # <-- NOSSO NOVO BEBÊ AQUI

    try:
        monitorar()
    except KeyboardInterrupt:
        encerrar_tudo()
