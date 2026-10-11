import time
from google import genai

# 1. Cole a sua chave de API aqui
API_KEY = "AIzaSyB6DHt17JKlzNsp7o7NVF5I8ikKQlKsu-Q"

# Inicializa o cliente do Gemini
client = genai.Client(api_key=API_KEY)
MODEL_ID = "gemini-3.8-flash" # Atualizado para o modelo mais recente suportado

# O texto exato que você solicitou
TEXTO = "Rogério Gonçalves e Evaldo Luiz"

# Definindo os três tons usando instruções de sistema
tons = {
    "normal": "Read the following text with a calm, neutral, and relaxed tone.",
    "engracada": "Read the following text with a cheerful, laughing, and highly enthusiastic tone.",
    "nervosa": "Read the following text with a frustrated, angry, and tense tone."
}

def gerar_audio(nome_do_tom, instrucao_de_tom, arquivo_saida):
    print(f"Gerando voz ({nome_do_tom})...")
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=[TEXTO],
        config={
            "response_modalities": ["AUDIO"],
            "system_instruction": instrucao_de_tom,
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "Kore"
                    }
                }
            }
        }
    )
    
    # Salva o arquivo de áudio recebido
    audio_data = response.candidates[0].content.parts[0].inline_data.data
    with open(arquivo_saida, "wb") as f:
        f.write(audio_data)
    print(f"✅ Arquivo salvo: {arquivo_saida}")

print("=== 1. GERANDO OS 3 TONS ===")
for nome_tom, instrucao in tons.items():
    gerar_audio(nome_tom, instrucao, f"voz_{nome_tom}.wav")

print("\n=== 2. INICIANDO O TESTE DE STRESS (1 MINUTO) ===")
print("Testando quantas requisições a sua chave aguenta em 60 segundos...")

tempo_inicial = time.time()
contador = 0

# Loop de benchmark que roda por exatamente 60 segundos
while time.time() - tempo_inicial < 60:
    try:
        client.models.generate_content(
            model=MODEL_ID,
            contents=[TEXTO],
            config={
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {
                            "voice_name": "Kore"
                        }
                    }
                }
            }
        )
        contador += 1
        print(f"Requisição {contador} concluída...")
    except Exception as e:
        print(f"\n⚠️ Limite de taxa (Rate Limit) atingido ou erro na requisição {contador + 1}!")
        print(f"Detalhe: {e}")
        break

print(f"\n🚀 Fim do teste: Você conseguiu processar {contador} requisições em 1 minuto.")
