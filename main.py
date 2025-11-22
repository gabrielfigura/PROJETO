import asyncio
import aiohttp
import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler
from telegram.error import TelegramError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from collections import Counter
import uuid

# Configurações do Bot (valores fixos para teste)
BOT_TOKEN = "8163319902:AAHE9LZ984JCIc-Lezl4WXR2FsGHPEFTxRQ"
CHAT_ID = "-1002597090660"
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"

# Inicializar o bot e a aplicação
bot = Bot(token=BOT_TOKEN)
application = Application.builder().token(BOT_TOKEN).build()

# Configuração de logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Histórico e estado
historico = []
empates_historico = []
ultimo_padrao_id = None
ultimo_resultado_id = None
sinais_ativos = []
placar = {
    "ganhos_seguidos": 0,
    "losses": 0,
    "empates": 0
}
rodadas_desde_erro = 0
ultima_mensagem_monitoramento = None
detecao_pausada = False
aguardando_validacao = False

# Mapeamento de outcomes para emojis
OUTCOME_MAP = {
    "PlayerWon": "🔵",
    "BankerWon": "🔴",
    "Tie": "🟡"
}

# Padrões (corrigido ID duplicado)
PADROES = [
    { "id": 7, "sequencia": ["🔴", "🔵", "🔴", "🔵", "🔴", "🔵"], "sinal": "🔴" },
    { "id": 8, "sequencia": ["🔵", "🔴", "🔵", "🔴", "🔵", "🔴"], "sinal": "🔵" },
    { "id": 9, "sequencia": ["🔴", "🔴", "🔴", "🔵", "🔵", "🔵", "🔴", "🔴", "🔴"], "sinal": "🔵" },
    { "id": 12, "sequencia": ["🔵", "🔵", "🔵", "🔴", "🔴", "🔴", "🔵", "🔵", "🔵"], "sinal": "🔴" },
]

@retry(stop=stop_after_attempt(7), wait=wait_exponential(multiplier=1, min=4, max=60), retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)))
async def fetch_resultado():
    """Busca o resultado mais recente da API com retry e timeout aumentado."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    return None, None, None, None
                data = await response.json()
                if 'data' not in data or 'result' not in data['data'] or 'outcome' not in data['data']['result']:
                    return None, None, None, None
                if 'id' not in data:
                    return None, None, None, None
                if data['data'].get('status') != 'Resolved':
                    return None, None, None, None
                resultado_id = data['id']
                outcome = data['data']['result']['outcome']
                player_score = data['data']['result'].get('playerDice', {}).get('score', 0)
                banker_score = data['data']['result'].get('bankerDice', {}).get('score', 0)
                if outcome not in OUTCOME_MAP:
                    return None, None, None, None
                resultado = OUTCOME_MAP[outcome]
                return resultado, resultado_id, player_score, banker_score
        except:
            return None, None, None, None

def verificar_tendencia(historico, sinal, tamanho_janela=8):
    if len(historico) < tamanho_janela:
        return True
    janela = historico[-tamanho_janela:]
    contagem = Counter(janela)
    total = contagem["🔴"] + contagem["🔵"]
    if total == 0:
        return True
    return True

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_sinal(sinal, padrao_id, resultado_id, sequencia):
    global ultima_mensagem_monitoramento, aguardando_validacao
    try:
        if ultima_mensagem_monitoramento:
            try:
                await bot.delete_message(chat_id=CHAT_ID, message_id=ultima_mensagem_monitoramento)
            except TelegramError:
                pass
            ultima_mensagem_monitoramento = None
        if aguardando_validacao or sinais_ativos:
            logging.info(f"Sinal bloqueado: aguardando validação ou sinal ativo (ID: {padrao_id})")
            return False
        sequencia_str = " ".join(sequencia)
        mensagem = f"""💡 CLEVER ANALISOU 💡
🧠 APOSTA EM: {sinal}
🛡️ Proteja o TIE 🟡
🤑 VAI ENTRAR DINHEIRO 🤑
⬇️ENTRA NA COMUNIDADE DO WHATSAPP ⬇️
https://chat.whatsapp.com/D61X4xCSDyk02srBHqBYXq"""
        keyboard = [[InlineKeyboardButton("EMPATES 🟡", callback_data="mostrar_empates")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        message = await bot.send_message(chat_id=CHAT_ID, text=mensagem, reply_markup=reply_markup)
        sinais_ativos.append({
            "sinal": sinal,
            "padrao_id": padrao_id,
            "resultado_id": resultado_id,
            "sequencia": sequencia,
            "enviado_em": asyncio.get_event_loop().time()
        })
        aguardando_validacao = True
        logging.info(f"Sinal enviado para padrão {padrao_id}: {sinal}")
        return message.message_id
    except TelegramError as e:
        logging.error(f"Erro ao enviar sinal: {e}")
        raise

async def mostrar_empates(update, context):
    """Handler para o botão EMPATES 🟡"""
    try:
        if not empates_historico:
            await update.callback_query.answer("Nenhum empate registrado ainda.")
            return
        empates_str = "\n".join([f"Empate {i+1}: 🟡 (🔵 {e['player_score']} x 🔴 {e['banker_score']})" for i, e in enumerate(empates_historico)])
        mensagem = f"📊 Histórico de Empates 🟡\n\n{empates_str}"
        await update.callback_query.message.reply_text(mensagem)
        await update.callback_query.answer()
    except TelegramError as e:
        logging.error(f"Erro ao mostrar empates: {e}")
        await update.callback_query.answer("Erro ao exibir empates.")

async def resetar_placar():
    global placar
    placar = {
        "ganhos_seguidos": 0,
        "losses": 0,
        "empates": 0
    }
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🔄 Placar resetado após 10 erros! Começando do zero.")
        await enviar_placar()
    except TelegramError:
        pass

async def enviar_placar():
    try:
        total_acertos = placar['ganhos_seguidos'] + placar['empates']
        total_sinais = total_acertos + placar['losses']
        precisao = (total_acertos / total_sinais * 100) if total_sinais > 0 else 0.0
        precisao = min(precisao, 100.0)
        mensagem_placar = f"""🚀 CLEVER PERFORMANCE 🚀
✅ACERTOS SEM GALE: {placar['ganhos_seguidos']}
🟡EMPATES: {placar['empates']}
🎯TOTAL ACERTOS: {total_acertos}
❌ERROS: {placar['losses']}
🔥PRECISÃO: {precisao:.2f}%"""
        await bot.send_message(chat_id=CHAT_ID, text=mensagem_placar)
    except TelegramError:
        pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_resultado(resultado, player_score, banker_score, resultado_id):
    global rodadas_desde_erro, ultima_mensagem_monitoramento, detecao_pausada, placar, ultimo_padrao_id, aguardando_validacao, empates_historico
    try:
        if resultado == "🟡":
            empates_historico.append({"player_score": player_score, "banker_score": banker_score})
            if len(empates_historico) > 50:
                empates_historico.pop(0)
        for sinal_ativo in sinais_ativos[:]:
            if sinal_ativo["resultado_id"] != resultado_id:
                if resultado == sinal_ativo["sinal"] or resultado == "🟡":
                    if resultado == "🟡":
                        placar["empates"] += 1
                    else:
                        placar["ganhos_seguidos"] += 1
                    mensagem_validacao = f"🤡ENTROU DINHEIRO🤡\n🎲 Resultado: 🔵 {player_score} x 🔴 {banker_score}"
                    await bot.send_message(chat_id=CHAT_ID, text=mensagem_validacao)
                    await enviar_placar()
                    ultimo_padrao_id = None
                    aguardando_validacao = False
                    sinais_ativos.remove(sinal_ativo)
                    detecao_pausada = False
                    logging.info(f"Sinal validado com sucesso para padrão {sinal_ativo['padrao_id']}")
                else:
                    placar["losses"] += 1
                    await bot.send_message(chat_id=CHAT_ID, text="❌ NÃO FOI DESSA❌")
                    await enviar_placar()
                    if placar["losses"] >= 10:
                        await resetar_placar()
                    ultimo_padrao_id = None
                    aguardando_validacao = False
                    sinais_ativos.remove(sinal_ativo)
                    detecao_pausada = False
                    logging.info(f"Sinal perdido para padrão {sinal_ativo['padrao_id']}, validação liberada")
                ultima_mensagem_monitoramento = None
            elif asyncio.get_event_loop().time() - sinal_ativo["enviado_em"] > 300:
                ultimo_padrao_id = None
                aguardando_validacao = False
                sinais_ativos.remove(sinal_ativo)
                detecao_pausada = False
                logging.info(f"Sinal expirado para padrão {sinal_ativo['padrao_id']}, validação liberada")
        if not sinais_ativos:
            aguardando_validacao = False
    except TelegramError:
        pass

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_monitoramento():
    global ultima_mensagem_monitoramento
    while True:
        try:
            if not sinais_ativos:
                if ultima_mensagem_monitoramento:
                    try:
                        await bot.delete_message(chat_id=CHAT_ID, message_id=ultima_mensagem_monitoramento)
                    except TelegramError:
                        pass
                message = await bot.send_message(chat_id=CHAT_ID, text="🔎MONITORANDO A MESA…")
                ultima_mensagem_monitoramento = message.message_id
            await asyncio.sleep(15)
        except TelegramError:
            await asyncio.sleep(15)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception_type(TelegramError))
async def enviar_relatorio():
    while True:
        try:
            total_acertos = placar['ganhos_seguidos'] + placar['empates']
            total_sinais = total_acertos + placar['losses']
            precisao = (total_acertos / total_sinais * 100) if total_sinais > 0 else 0.0
            precisao = min(precisao, 100.0)
            msg = f"""🚀 CLEVER PERFORMANCE 🚀
✅ACERTOS SEM GALE: {placar['ganhos_seguidos']}
🟡EMPATES: {placar['empates']}
🎯TOTAL ACERTOS: {total_acertos}
❌ERROS: {placar['losses']}
🔥PRECISÃO: {precisao:.2f}%"""
            await bot.send_message(chat_id=CHAT_ID, text=msg)
        except TelegramError:
            pass
        await asyncio.sleep(3600)

async def enviar_erro_telegram(erro_msg):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=f"❌ Erro detectado: {erro_msg}")
    except TelegramError:
        pass

async def main():
    global historico, ultimo_padrao_id, ultimo_resultado_id, rodadas_desde_erro, detecao_pausada, aguardando_validacao
    application.add_handler(CallbackQueryHandler(mostrar_empates, pattern="mostrar_empates"))
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    asyncio.create_task(enviar_relatorio())
    asyncio.create_task(enviar_monitoramento())
    try:
        await bot.send_message(chat_id=CHAT_ID, text="🚀 Bot iniciado com sucesso!")
    except TelegramError:
        pass
    while True:
        try:
            resultado, resultado_id, player_score, banker_score = await fetch_resultado()
            if not resultado or not resultado_id:
                await asyncio.sleep(2)
                continue
            if resultado_id == ultimo_resultado_id:
                await asyncio.sleep(2)
                continue
            ultimo_resultado_id = resultado_id
            historico.append(resultado)
            if len(historico) > 50:
                historico.pop(0)
            await enviar_resultado(resultado, player_score, banker_score, resultado_id)
            if not detecao_pausada and not aguardando_validacao and not sinais_ativos:
                for padrao in PADROES:
                    seq_len = len(padrao["sequencia"])
                    if len(historico) >= seq_len:
                        if historico[-seq_len:] == padrao["sequencia"] and padrao["id"] != ultimo_padrao_id:
                            if verificar_tendencia(historico, padrao["sinal"]):
                                enviado = await enviar_sinal(padrao["sinal"], padrao["id"], resultado_id, padrao["sequencia"])
                                if enviado:
                                    ultimo_padrao_id = padrao["id"]
                                    break
            await asyncio.sleep(2)
        except Exception as e:
            await enviar_erro_telegram(str(e))
            await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot encerrado pelo usuário")
    except Exception as e:
        logging.error(f"Erro fatal no bot: {e}")
        asyncio.run(enviar_erro_telegram(f"Erro fatal no bot: {e}"))
