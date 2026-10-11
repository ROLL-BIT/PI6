import random
import threading
import socket
import json
import serial
import serial.tools.list_ports
import time
import os

# --- MODO NUVEM (SEM TELA GRÁFICA) ---
# Impede que a VPS crashe por tentar abrir uma janela de programa
MODO_HEADLESS = True

if not MODO_HEADLESS:
    import tkinter as tk

# --- VARIÁVEIS GLOBAIS DE CONEXÃO ---
esp32 = None
conexao_ativa = False
porta_atual = ""
BAUD_RATE = 115200

# --- CONFIGURAÇÕES DA MATRIZ ---
SIZE = 16
LED = 20
offset_x = 0; offset_y = 0
limit_left_active = False; limit_right_active = False
limit_down_active = False; limit_up_active = False
limit_far_active = False; limit_near_active = False    
indicator_state = False; is_talking = False
matriz_virtual = [[0 for _ in range(SIZE)] for _ in range(SIZE)]

# --- INTERFACE TKINTER (Só abre se MODO_HEADLESS for False) ---
if not MODO_HEADLESS:
    root = tk.Tk()
    root.title("Rosto 16x16 - Nuvem")
    root.configure(bg="black")
    canvas = tk.Canvas(root, width=SIZE*LED, height=SIZE*LED, bg="black", highlightthickness=0)
    canvas.pack()
    status_label = tk.Label(root, text="A INICIAR SISTEMA...", fg="yellow", bg="black", font=("Arial", 12, "bold"))
    status_label.pack(fill=tk.X, pady=5)
    leds = []
    for y in range(SIZE):
        row = []
        for x in range(SIZE):
            row.append(canvas.create_rectangle(x*LED, y*LED, x*LED+LED, y*LED+LED, fill="black", outline="#222222"))
        leds.append(row)

# ==============================================================================
# MOTOR DE CONEXÃO
# ==============================================================================
def manter_conexao():
    global esp32, conexao_ativa, porta_atual
    if not conexao_ativa:
        portas_disponiveis = [p.device for p in serial.tools.list_ports.comports() 
                              if "COM" in p.device or "USB" in p.device or "ACM" in p.device]
        
        for porta in portas_disponiveis:
            try:
                temp_esp = serial.Serial(porta, BAUD_RATE, write_timeout=0.1)
                time.sleep(1.5) 
                esp32 = temp_esp; conexao_ativa = True; porta_atual = porta
                
                print("esp32 ok")
                if not MODO_HEADLESS: status_label.config(text=f"esp32 ok ({porta_atual})", fg="lime")
                break
            except Exception:
                pass 
        
        if not conexao_ativa:
            if not MODO_HEADLESS and status_label.cget("text") != "esp32 OFF":
                status_label.config(text="esp32 OFF", fg="red")
            
    if not MODO_HEADLESS: root.after(2000, manter_conexao)

def loop_manter_conexao_headless():
    while True:
        manter_conexao()
        time.sleep(2)

def set_led(x, y, state=True):
    if 0 <= x < SIZE and 0 <= y < SIZE:
        matriz_virtual[y][x] = 1 if state else 0
        if not MODO_HEADLESS:
            color = "lime" if state else "black"
            canvas.itemconfig(leds[y][x], fill=color)

def enviar_para_esp32():
    global conexao_ativa, esp32
    if not conexao_ativa or esp32 is None: return

    buffer = bytearray(37)
    matriz_virada = [[matriz_virtual[15-y][15-x] for x in range(16)] for y in range(16)]
    
    for col in range(16):
        byte_topo = 0; byte_fundo = 0
        for linha in range(8):
            if matriz_virada[linha][col]: byte_topo |= (1 << linha)
            if matriz_virada[linha+8][col]: byte_fundo |= (1 << linha)
        buffer[col] = byte_topo
        buffer[col + 16] = byte_fundo

    buffer[32] = 2; buffer[33] = 0; buffer[34] = 2; buffer[35] = 0; buffer[36] = 0 

    try:
        esp32.write(buffer)
    except Exception:
        if conexao_ativa:
            conexao_ativa = False
            print("esp32 OFF")
            if not MODO_HEADLESS: status_label.config(text="esp32 OFF", fg="red")
            try: esp32.close()
            except: pass
            esp32 = None

# ==============================================================================
# LÓGICA DE ANIMAÇÃO 
# ==============================================================================
def clear():
    for y in range(SIZE):
        for x in range(SIZE):
            if y == 15 and x in [0, 15]: continue
            if y == 0 and x in [0, 1, 14, 15]: continue
            set_led(x, y, False)

def update_indicators():
    global indicator_state
    indicator_state = not indicator_state
    set_led(0, 15, indicator_state if limit_left_active else False)
    set_led(15, 15, indicator_state if limit_right_active else False)
    set_led(0, 0, indicator_state if limit_down_active else False)
    set_led(15, 0, indicator_state if limit_up_active else False)
    set_led(1, 0, indicator_state if limit_far_active else False)
    set_led(14, 0, indicator_state if limit_near_active else False)
    enviar_para_esp32()
    if not MODO_HEADLESS: root.after(250, update_indicators)

def loop_indicators_headless():
    while True:
        update_indicators()
        time.sleep(0.25)

def draw_face():
    clear()
    for x in range(4,6):
        for y in range(3,5): set_led(x+offset_x,y+offset_y)
    for x in range(10,12):
        for y in range(3,5): set_led(x+offset_x,y+offset_y)
    for x in range(5,11): set_led(x+offset_x,9+offset_y)
    enviar_para_esp32()

def eyes_closed():
    clear()
    for x in range(4,6): set_led(x+offset_x,4+offset_y)
    for x in range(10,12): set_led(x+offset_x,4+offset_y)
    for x in range(5,11): set_led(x+offset_x,9+offset_y)
    enviar_para_esp32()

def blink():
    eyes_closed()
    if not MODO_HEADLESS: root.after(200, draw_face)
    else: time.sleep(0.2); draw_face()

def auto_blink():
    if not MODO_HEADLESS:
        if not is_talking: blink()
        root.after(random.randint(2000,10000), auto_blink)
    else:
        while True:
            if not is_talking: blink()
            time.sleep(random.randint(2000,10000)/1000.0)

def animate_mouth():
    if not is_talking:
        draw_face()
        return

    clear()
    for x in range(4,6):
        for y in range(3,5): set_led(x+offset_x,y+offset_y)
    for x in range(10,12):
        for y in range(3,5): set_led(x+offset_x,y+offset_y)

    mouth = random.randint(0,2)
    if mouth == 0:
        for x in range(5,11): set_led(x+offset_x,9+offset_y)
    elif mouth == 1:
        for x in range(5,11):
            set_led(x+offset_x,9+offset_y)
            set_led(x+offset_x,10+offset_y)
    else:
        for x in range(6,10):
            set_led(x+offset_x,8+offset_y)
            set_led(x+offset_x,9+offset_y)
            set_led(x+offset_x,10+offset_y)

    enviar_para_esp32()
    
    if not MODO_HEADLESS:
        if is_talking: root.after(150, animate_mouth)

def loop_animate_mouth_headless():
    while True:
        if is_talking:
            animate_mouth()
            time.sleep(0.15)
        else:
            time.sleep(0.1)

# --- THREADS DE UDP ---
def udp_thread_visao():
    global offset_x, offset_y, limit_left_active, limit_right_active, limit_down_active, limit_up_active, limit_far_active, limit_near_active
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 5005))
    while True:
        try:
            dados_recebidos, _ = sock.recvfrom(1024)
            mensagem = json.loads(dados_recebidos.decode('utf-8'))
            if "centro_x" in mensagem:
                cx = mensagem["centro_x"]; cy = mensagem["centro_y"]; dist = mensagem["distancia_cm"]
                
                limit_left_active = True if cx < 120 else False
                limit_right_active = True if cx > 500 else False
                limit_down_active = True if cy > 350 else False
                limit_up_active = True if cy <= 200 else False
                limit_far_active = True if dist > 80 else False
                limit_near_active = True if dist < 40 else False

                novo_offset_x = max(-4, min(4, int((cx - 320) / 75))) 
                novo_offset_y = max(-3, min(4, int((cy - 240) / 55)))
                
                if novo_offset_x != offset_x or novo_offset_y != offset_y:
                    offset_x = novo_offset_x; offset_y = novo_offset_y
                    if not is_talking:
                        if not MODO_HEADLESS: root.after(0, draw_face)
                        else: draw_face()
        except Exception: pass 

def udp_thread_voz():
    global is_talking
    sock_voz = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_voz.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_voz.bind(("127.0.0.1", 5007))
    while True:
        try:
            data, _ = sock_voz.recvfrom(1024)
            status = data.decode('utf-8')
            if "INICIOU_FALA" in status:
                if not is_talking:
                    is_talking = True
                    if not MODO_HEADLESS: root.after(0, animate_mouth)
            elif "TERMINOU_FALA" in status:
                is_talking = False
        except Exception: pass

threading.Thread(target=udp_thread_visao, daemon=True).start()
threading.Thread(target=udp_thread_voz, daemon=True).start()

print("[SISTEMA] Módulo Ponte de Interface Iniciado")

if not MODO_HEADLESS:
    manter_conexao()
    update_indicators()
    draw_face()
    root.after(random.randint(2000,10000), auto_blink)
    root.mainloop()
else:
    threading.Thread(target=loop_manter_conexao_headless, daemon=True).start()
    threading.Thread(target=loop_indicators_headless, daemon=True).start()
    threading.Thread(target=auto_blink, daemon=True).start()
    threading.Thread(target=loop_animate_mouth_headless, daemon=True).start()
    draw_face()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SISTEMA] Módulo Encerrado.")
