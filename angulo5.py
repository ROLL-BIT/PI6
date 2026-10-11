import cv2
import numpy as np
import pickle
import os
import math
import time
import socket
import json
import threading  # <--- NOVA IMPORTAÇÃO PARA ESCUTAR O CÉREBRO

# --- CONFIGURAÇÃO DO SOCKET UDP ---
UDP_IP = "127.0.0.1" 
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# ----------------------------------

# --- CONFIGURAÇÕES BÁSICAS ---
YUNET_MODEL = "face_detection_yunet_2023mar.onnx"
SFACE_MODEL = "face_recognition_sface_2021dec.onnx"
DB_PATH = "faces_leves.pkl"

THRESH_RECOG = 0.36 
DISTANCIA_MAX_MEMORIA = 80 

# --- CONFIGURAÇÕES DA CÂMERA ---
LARGURA_REAL_FACE = 15.0  
DIST_FOCAL_PIXELS = 766   

print("[INFO] Carregando modelos YuNet e SFace...")
detector = cv2.FaceDetectorYN.create(YUNET_MODEL, "", (320, 320), score_threshold=0.6)
recognizer = cv2.FaceRecognizerSF.create(SFACE_MODEL, "")

# --- CARREGAMENTO DO BANCO DE DADOS ---
try:
    with open(DB_PATH, "rb") as f:
        data = pickle.load(f)
    embeddings_db, nomes_db = data["embeddings"], data["names"]
    print(f"[INFO] Banco carregado: {len(nomes_db)} rostos encontrados.")
except Exception as e:
    print(f"[AVISO] Banco de dados vazio ou não encontrado. Criando um novo.")
    embeddings_db, nomes_db = [], []

def salvar_banco():
    """Salva as alterações no arquivo faces_leves.pkl em tempo real"""
    with open(DB_PATH, "wb") as f:
        pickle.dump({"embeddings": embeddings_db, "names": nomes_db}, f)

# --- THREAD DE APRENDIZAGEM E ESQUECIMENTO (ESCUTA A PORTA 5012) ---
rosto_para_aprender = None

def escutar_pedidos_de_treino():
    global rosto_para_aprender
    sock_treino = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_treino.bind((UDP_IP, 5012))
    print("[VISÃO] Pronta para aprender ou esquecer rostos na porta 5012...")
    while True:
        try:
            dados, _ = sock_treino.recvfrom(1024)
            msg = json.loads(dados.decode('utf-8'))
            comando = msg.get("comando")
            nome_alvo = msg.get("nome")
            
            if comando == "aprender":
                rosto_para_aprender = nome_alvo
                print(f"\n[VISÃO] ORDEM DO CÉREBRO RECEBIDA! Capturando rosto de: {rosto_para_aprender}")
                
            elif comando == "esquecer":
                print(f"\n[VISÃO] ORDEM DO CÉREBRO RECEBIDA! Apagando rosto de: {nome_alvo}")
                apagou = False
                
                # Remove de trás para frente para não quebrar os índices do array
                for i in range(len(nomes_db) - 1, -1, -1):
                    if nomes_db[i].lower() == nome_alvo.lower():
                        nomes_db.pop(i)
                        embeddings_db.pop(i)
                        apagou = True
                
                if apagou:
                    salvar_banco()
                    print(f"[VISÃO] SUCESSO! A biometria de {nome_alvo} foi deletada definitivamente.")
                else:
                    print(f"[VISÃO] {nome_alvo} não estava no banco de dados.")
        except Exception:
            pass

threading.Thread(target=escutar_pedidos_de_treino, daemon=True).start()
# ----------------------------------------------------

memoria_rostos_anteriores = []

cap = cv2.VideoCapture(0)
print("[INFO] Câmera ligada. Pressione 'ESC' para sair.")

prev_time = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # --- CÁLCULO DE FPS ---
    current_time = time.time()
    fps = 1 / (current_time - prev_time) if prev_time != 0 else 0
    prev_time = current_time

    h, w, _ = frame.shape
    detector.setInputSize((w, h))

    faces = detector.detect(frame)
    rostos_frescos = []

    if faces[1] is not None:
        
        # ==================================================================
        # A MÁGICA DA APRENDIZAGEM ACONTECE AQUI
        # ==================================================================
        if rosto_para_aprender is not None:
            # Pega o primeiro rosto detectado (presume-se ser a pessoa na frente)
            face_detectada = faces[1][0] 
            
            print(f"[VISÃO] Extraindo biometria de {rosto_para_aprender}...")
            aligned = recognizer.alignCrop(frame, face_detectada)
            embedding_novo = recognizer.feature(aligned)
            
            # Adiciona à memória RAM e salva no HD
            embeddings_db.append(embedding_novo)
            nomes_db.append(rosto_para_aprender)
            salvar_banco()
            
            print(f"[VISÃO] SUCESSO! Rosto de {rosto_para_aprender} memorizado!")
            rosto_para_aprender = None # Limpa a variável para não tirar foto repetida
        # ==================================================================

        for face in faces[1]:
            x = int(face[0])
            y = int(face[1])
            w_box = int(face[2])
            h_box = int(face[3])
            
            # Matemática do Servo e Distância
            cx = x + (w_box // 2)
            cy = y + (h_box // 2)
            
            if w_box > 0:
                distancia = (LARGURA_REAL_FACE * DIST_FOCAL_PIXELS) / w_box
            else:
                distancia = 0.0
            
            # Extração biométrica
            aligned = recognizer.alignCrop(frame, face)
            embedding_atual = recognizer.feature(aligned)
            
            nome_detectado = "Desconhecido"
            melhor_score = 0
            
            # 1º Tentativa: SFace
            if len(embeddings_db) > 0:
                for i, db_emb in enumerate(embeddings_db):
                    score = recognizer.match(embedding_atual, db_emb, cv2.FaceRecognizerSF_FR_COSINE)
                    if score > melhor_score:
                        melhor_score = score
                        if score > THRESH_RECOG:
                            nome_detectado = nomes_db[i]

            # 2º Tentativa: Memória Espacial
            if nome_detectado == "Desconhecido":
                for mem_cx, mem_cy, mem_nome in memoria_rostos_anteriores:
                    dist_pixels = math.hypot(cx - mem_cx, cy - mem_cy)
                    
                    if dist_pixels < DISTANCIA_MAX_MEMORIA and mem_nome != "Desconhecido":
                        nome_detectado = mem_nome
                        break
            
            rostos_frescos.append((cx, cy, nome_detectado))

            # --- ENVIO UDP PARA A INTERFACE E BANCO ---
            dados_exportacao = {
                "nome": nome_detectado,
                "centro_x": cx,
                "centro_y": cy,
                "distancia_cm": round(distancia, 1),
                "reconhecido": True if nome_detectado != "Desconhecido" else False
            }
            mensagem = json.dumps(dados_exportacao).encode('utf-8')
            
            # Disparos Manuais
            sock.sendto(mensagem, (UDP_IP, 5005)) # Vai para a Interface Gráfica
            sock.sendto(mensagem, (UDP_IP, 5008)) # Vai para o Banco de Dados           
            sock.sendto(mensagem, (UDP_IP, 5009)) # Vai para o Gravador

            # --- INTERFACE GRÁFICA ---
            cor = (0, 255, 0) if nome_detectado != "Desconhecido" else (0, 0, 255)
            cv2.rectangle(frame, (x, y), (x + w_box, y + h_box), cor, 2)
            cv2.circle(frame, (cx, cy), 4, (0, 255, 255), -1)
            
            cv2.putText(frame, f"{nome_detectado}", (x, y - 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cor, 2)
            cv2.putText(frame, f"Servo: X:{cx} Y:{cy}", (x, y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            cv2.putText(frame, f"Dist: {distancia:.1f}cm", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

    memoria_rostos_anteriores = rostos_frescos

    # FPS na tela
    cv2.putText(frame, f"FPS: {int(fps)}", (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    cv2.imshow("Sistema Visao -> Servos", frame)

    if cv2.waitKey(1) == 27: 
        break

cap.release()
cv2.destroyAllWindows()
sock.close()
