import socket

UDP_IP = "127.0.0.1"
UDP_PORT = 5006

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(60.0) # Tempo de sobra para frases longas

print("--- Terminal de Monitoramento de Voz ---")

while True:
    msg = input("\n📝 Digite sua frase: ")
    if msg.lower() == 'sair': break
    if not msg.strip(): continue

    try:
        # Envia o comando
        sock.sendto(msg.encode('utf-8'), (UDP_IP, UDP_PORT))
        
        # Loop para capturar os múltiplos status do servidor
        while True:
            data, server = sock.recvfrom(1024)
            status = data.decode('utf-8')

            if "INICIOU_FALA" in status:
                print("📢 [SISTEMA]: Começou a falar agora!")
            
            elif "TERMINOU_FALA" in status:
                print("🤫 [SISTEMA]: Ficou em silêncio. (falado ok)")
                break # Sai do loop de espera e libera o input
            
            elif "ERRO" in status:
                print(f"❌ {status}")
                break

    except socket.timeout:
        print("⚠️ Timeout: O servidor não respondeu.")
