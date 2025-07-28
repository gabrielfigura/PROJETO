import telegram
import asyncio
import requests
from datetime import datetime
import logging
from tenacity import retry, stop_after_attempt, wait_fixed

# Configuração de logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot config
TOKEN = "7703975421:AAG-CG5Who2xs4NlevJqB5TNvjjzeUEDz8o"
CHAT_ID = "-1002859771274"
bot = telegram.Bot(token=TOKEN)

# Mapeamento de cores da API
MAP_CORES = {
    "Player": "🔵",
    "Banker": "🔴",
    "Tie": "🟡"
}

# Lista de padrões a detectar
PADROES = [  # apenas os 3 primeiros mostrados por espaço; inclui os 50 no código real
    {"id": 1, "sequencia": ["🔴", "🔴", "🔴"], "acao": "Entrar a favor"},
    {"id": 2, "sequencia": ["🔵", "🔴", "🔵"], "acao": "Entrar no oposto do último"},
    {"id": 3, "sequencia": ["🔴", "🔴", "🔵"], "acao": "Entrar contra"},
   {"id": 4, "sequencia": ["🔵", "🔵", "🔴", "🔴"], "acao": "Entrar no lado que inicia"},
  {"id": 5, "sequencia": ["🔴", "🔴", "🔴", "🔵"], "acao": "Seguir rompimento"},
  {"id": 6, "sequencia": ["🔵", "🔵", "🔵"], "acao": "Entrar a favor"},
  {"id": 7, "sequencia": ["🔴", "🔵", "🔴"], "acao": "Seguir alternância"},
  {"id": 8, "sequencia": ["🔴", "🔵", "🔵"], "acao": "Seguir nova cor"},
  {"id": 9, "sequencia": ["🔴", "🔴", "🟡"], "acao": "Seguir 🔴"},
  {"id": 10, "sequencia": ["🔴", "🔵", "🟡", "🔴"], "acao": "Ignorar Tie e seguir 🔴"},
  {"id": 11, "sequencia": ["🔵", "🔴", "🔴"], "acao": "Seguir 🔴"},
  {"id": 12, "sequencia": ["🔴", "🔵", "🔵"], "acao": "Seguir 🔵"},
  {"id": 13, "sequencia": ["🔵", "🔵", "🔴", "🔵"], "acao": "Voltar para 🔵"},
  {"id": 14, "sequencia": ["🔴", "🟡", "🔴"], "acao": "Seguir 🔴"},
  {"id": 15, "sequencia": ["🔴", "🔴", "🔴", "🔴"], "acao": "Entrar a favor"},
  {"id": 16, "sequencia": ["🔵", "🔵", "🔵", "🔴"], "acao": "Entrar contra 🔴"},
  {"id": 17, "sequencia": ["🔴", "🔵", "🔴", "🔵"], "acao": "Seguir alternância"},
  {"id": 18, "sequencia": ["🔴", "🔵", "🔵", "🔴"], "acao": "Entrar contra 🔵"},
  {"id": 19, "sequencia": ["🔵", "🟡", "🔵"], "acao": "Seguir 🔵"},
  {"id": 20, "sequencia": ["🔴", "🔵", "🟡", "🔵", "🔵"], "acao": "Seguir 🔵"},
  {"id": 21, "sequencia": ["🔵", "🔵", "🔴", "🔴", "🔵"], "acao": "Seguir 🔵"},
  {"id": 22, "sequencia": ["🔴", "🔴", "🔵", "🔴"], "acao": "Seguir 🔴"},
  {"id": 23, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔴"], "acao": "Seguir 🔴"},
  {"id": 24, "sequencia": ["🔴", "🔵", "🔴", "🔴"], "acao": "Seguir 🔴"},
  {"id": 25, "sequencia": ["🔴", "🔴", "🔴", "🟡", "🔴"], "acao": "Seguir 🔴"},
  {"id": 26, "sequencia": ["🔵", "🔴", "🔴", "🔵", "🔵"], "acao": "Seguir pares"},
  {"id": 27, "sequencia": ["🔴", "🟡", "🔵"], "acao": "Seguir 🔵"},
  {"id": 28, "sequencia": ["🔵", "🔵", "🟡", "🔵", "🔵"], "acao": "Seguir 🔵"},
  {"id": 29, "sequencia": ["🔴", "🔴", "🔵", "🔵", "🔴"], "acao": "Seguir 🔴"},
  {"id": 30, "sequencia": ["🔵", "🔵", "🔴", "🔵", "🔵"], "acao": "Seguir 🔵"},
  {"id": 31, "sequencia": ["🔴", "🔴", "🔴", "🔴", "🔴"], "acao": "Seguir 🔴"},
  {"id": 32, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔵"], "acao": "Seguir alternância"},
  {"id": 33, "sequencia": ["🔴", "🔵", "🔴", "🟡", "🔵"], "acao": "Seguir 🔵"},
  {"id": 34, "sequencia": ["🔵", "🔵", "🔴", "🔴", "🔴"], "acao": "Seguir 🔴"},
  {"id": 35, "sequencia": ["🔴", "🟡", "🔴", "🔵"], "acao": "Seguir 🔵"},
  {"id": 36, "sequencia": ["🔴", "🔴", "🟡", "🔵", "🔵"], "acao": "Seguir 🔵"},
  {"id": 37, "sequencia": ["🔵", "🔴", "🟡", "🔵", "🔴"], "acao": "Seguir alternância"},
  {"id": 38, "sequencia": ["🔴", "🔴", "🔴", "🔵", "🔴", "🔴"], "acao": "Seguir 🔴"},
  {"id": 39, "sequencia": ["🔵", "🔵", "🔵", "🔴", "🔵"], "acao": "Voltar para 🔵"},
  {"id": 40, "sequencia": ["🔴", "🔴", "🔴", "🟡", "🔵", "🔵"], "acao": "Seguir 🔵"},
  {"id": 41, "sequencia": ["🔴", "🔵", "🔴", "🔴", "🔵"], "acao": "Seguir 🔵"},
  {"id": 42, "sequencia": ["🔵", "🔴", "🔴", "🔵", "🔵", "🔴", "🔴"], "acao": "Seguir pares"},
  {"id": 43, "sequencia": ["🔴", "🔴", "🔵", "🔵", "🔴", "🔴"], "acao": "Seguir ciclo"},
  {"id": 44, "sequencia": ["🔵", "🔴", "🔴", "🔴", "🔵"], "acao": "Seguir 🔴"},
  {"id": 45, "sequencia": ["🔴", "🔵", "🟡", "🔴", "🔴"], "acao": "Seguir 🔴"},
  {"id": 46, "sequencia": ["🔴", "🔴", "🔵", "🔵", "🔴", "🔴", "🔵", "🔵"], "acao": "Seguir pares"},
  {"id": 47, "sequencia": ["🔵", "🔵", "🔵", "🔴", "🔴", "🔴", "🔵"], "acao": "Novo início"},
  {"id": 48, "sequencia": ["🔴", "🔴", "🔴", "🔵", "🔴", "🔴"], "acao": "Seguir 🔴"},
  {"id": 49, "sequencia": ["🔵", "🔴", "🔴", "🔵", "🔵", "🔴", "🔴"], "acao": "Seguir padrão 2x"},
  {"id": 50, "sequencia": ["🔴", "🔴", "🟡", "🔵", "🔵", "🔴"], "acao": "Seguir 🔴"}
]

historico = []
placar = []
ultimo_sinal = None

# Buscar dados da API
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def buscar_resultado():
    url = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"
    resp = requests.get(url)
    resp.raise_for_status()
    dados = resp.json()

    resultado = dados["data"]["result"]["outcome"]
    return MAP_CORES.get(resultado)

# Verificar se há algum padrão
def detectar_padrao():
    for padrao in PADROES:
        seq = padrao["sequencia"]
        if historico[-len(seq):] == seq:
            return padrao
    return None

# Enviar sinal para o Telegram
async def enviar_sinal(padrao):
    cor_base = padrao["sequencia"][-1]
    acao = padrao["acao"]

    mensagem = f"""📡 *Padrão Detectado!*
Sequência: {"".join(padrao["sequencia"])}
🎯 Ação recomendada: *{acao}*
🕑 {datetime.now().strftime('%H:%M:%S')}
"""
    await bot.send_message(chat_id=CHAT_ID, text=mensagem, parse_mode=telegram.ParseMode.MARKDOWN)

# Enviar resultado após o sinal
async def enviar_resultado(cor_esperada, cor_real):
    global placar

    if cor_real == cor_esperada:
        placar.append("✅")
        status = "💰✅ BATEU ✅💰"
    else:
        placar = []  # Zera após erro
        status = "❌ ERRO ❌"

    texto = f"{status}\nResultado: {cor_real}\nPlacar: {' '.join(placar)}"
    await bot.send_message(chat_id=CHAT_ID, text=texto)

# Função principal
async def monitorar():
    global ultimo_sinal
    while True:
        try:
            cor = await buscar_resultado()
            if not cor:
                await asyncio.sleep(3)
                continue

            if not historico or historico[-1] != cor:
                historico.append(cor)
                logger.info(f"Novo resultado: {cor} | Histórico: {historico[-10:]}")

                if len(historico) >= 3 and not ultimo_sinal:
                    padrao = detectar_padrao()
                    if padrao:
                        ultimo_sinal = padrao
                        await enviar_sinal(padrao)

                elif ultimo_sinal:
                    cor_esperada = ultimo_sinal["sequencia"][-1]
                    await enviar_resultado(cor_esperada, cor)
                    ultimo_sinal = None

            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Erro: {e}")
            await asyncio.sleep(5)

# Executar
if __name__ == "__main__":
    asyncio.run(monitorar())
