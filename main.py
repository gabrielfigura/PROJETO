import requests
import time
import json
import telebot
from datetime import datetime
import threading


# ================= CONFIGURAÇÕES =================
API_URL = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"  # API não oficial (funciona em 12/2025)
TELEGRAM_TOKEN = "8163319902:AAHE9LZ984JCIc-Lezl4WXR2FsGHPEFTxRQ" # Bot feito no @BotFather
CHAT_ID = "-1002597090660"        # ID do canal ou grupo Telegram

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Placares
sem_gale = com_gale1 = com_gale2 = perdas = 0
gale_ativo = 0
ultimo_sinal = None
historico = []

def get_ultimos_resultados():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(API_URL, headers=headers, timeout=10)
        data = r.json()
        resultados = []
        for jogo in data['results'][-20:]:  # últimos 20
            player = jogo['playerTotal']
            banker = jogo['bankerTotal']
            if player > banker:
                resultados.append("P")
            elif banker > player:
                resultados.append("B")
            else:
                resultados.append("T")  # Tie = acerto
        return resultados[::-1]  # mais antigo primeiro
    except:
        return historico[-20:] if historico else ["P","B","T","P","B"]

def analisar_tendencia():
    resultados = get_ultimos_resultados()
    if len(resultados) < 8:
        return None, "Aguardando mais dados..."

    # Estratégias profissionais reais
    p_streak = b_streak = 0
    ultimo = resultados[-1]
    for r in reversed(resultados):
        if r == ultimo:
            if ultimo == "P": p_streak += 1
            if ultimo == "B": b_streak += 1
        else:
            break

    # Choppiness Index (medir se está "choppy" ou em tendência)
    range_14 = len(set(resultados[-14:]))
    choppy = range_14 > 10

    # Estratégia combinada usada por high rollers
    sinal = None
    confianca = ""

    # 1. Streak forte (4+ seguidos)
    if p_streak >= 4:
        sinal = "B"
        confianca = "Quebra de streak Player (4+)"
    elif b_streak >= 4:
        sinal = "P"
        confianca = "Quebra de streak Banker (4+)"
    
    # 2. Chop alternado forte
    elif "PBPB" in "".join(resultados[-8:]) or "BPBP" in "".join(resultados[-8:]):
        sinal = ultimo  # seguir o chop
        confianca = "Chop forte detectado - seguir último"

    # 3. Após 3 alternados, esperar repetição
    elif resultados[-3:] == ["P","B","P"]:
        sinal = "B"
        confianca = "Padrão PBP → próximo B"
    elif resultados[-3:] == ["B","P","B"]:
        sinal = "P"
        confianca = "Padrão BPB → próximo P"

    # 4. Após 2 Ties seguidos → forte tendência
    elif resultados[-2:] == ["T","T"]:
        sinal = "P" if resultados[-3] == "B" else "B"
        confianca = "Dois Ties → seguir oposto do anterior"

    if sinal and sinal != "T":
        return sinal, confianca
    return None, "Sem sinal claro (evitando choppy)" if choppy else "Aguardando padrão forte"

def enviar_sinal(sinal, motivo):
    global ultimo_sinal, gale_ativo
    ultimo_sinal = sinal
    gale_ativo = 0

    texto = f"""
🎰 NOVO SINAL BAC BO 🎰
⚡ Aposte agora → { 'PLAYER 🟦' if sinal == 'P' else 'BANKER 🟥' }
📊 Motivo: {motivo}
⏰ {datetime.now().strftime('%H:%M:%S')}
🔥 Entre com força!
    """
    bot.send_message(CHAT_ID, texto, parse_mode='HTML')

def atualizar_placar(acertou, com_quant_gale):
    global sem_gale, com_gale1, com_gale2, perdas
    if acertou:
        if com_quant_gale == 0:
            sem_gale += 1
            status = "✅ ACERTO SEM GALE"
        elif com_quant_gale == 1:
            com_gale1 += 1
            status = "✅ RECUPEROU NO 1º GALE"
        elif com_quant_gale == 2:
            com_gale2 += 1
            status = "⚡ RECUPEROU NO 2º GALE"
    else:
        perdas += 1
        status = "❌ PERDA TOTAL (perdeu 2 gales)"

    placar = f"""
📊 PLACAR ATUALIZADO - BAC BO BOT
✅ Sem Gale: {sem_gale}
✅ Com 1 Gale: {com_gale1}
⚡ Com 2 Gale: {com_gale2}
❌ Perdas: {perdas}
💚 Taxa de Acerto (considerando gale): {((sem_gale + com_gale1 + com_gale2)/(sem_gale + com_gale1 + com_gale2 + perdas)*100):.1f}%
💀 Perda real: {perdas}
    """
    bot.send_message(CHAT_ID, f"{status}\n{placar}", parse_mode='HTML')

def monitorar():
    global gale_ativo, ultimo_sinal, historico

    while True:
        try:
            resultados = get_ultimos_resultados()
            ultimo_resultado = resultados[-1]
            historico = resultados

            # Verificar se saiu o resultado do último sinal
            if ultimo_sinal and len(historico) > len([h for h in historico if h != ultimo_resultado]):
                # Resultado saiu!
                acertou = (ultimo_resultado == ultimo_sinal or ultimo_resultado == "T")
                
                if acertou:
                    atualizar_placar(True, gale_ativo)
                    gale_ativo = 0
                    ultimo_sinal = None
                else:
                    if gale_ativo < 2:
                        gale_ativo += 1
                        novo_sinal = ultimo_sinal
                        bot.send_message(CHAT_ID, f"🔄 GALE {gale_ativo} → Continuar no { 'PLAYER 🟦' if novo_sinal=='P' else 'BANKER 🟥' }")
                    else:
                        atualizar_placar(False, 0)
                        gale_ativo = 0
                        ultimo_sinal = None

            # Gerar novo sinal apenas se não estiver em gale
            if not ultimo_sinal:
                sinal, motivo = analisar_tendencia()
                if sinal:
                    enviar_sinal(sinal, motivo)

            time.sleep(8)  # Bac Bo roda a cada ~35-45s, verificamos a cada 8s

        except Exception as e:
            print("Erro:", e)
            time.sleep(10)

# Iniciar bot
@bot.message_handler(commands=['placar'])
def placar_cmd(message):
    placar = f"""
📊 PLACAR BAC BO BOT
✅ Sem Gale: {sem_gale}
✅ Com 1 Gale: {com_gale1}
⚡ Com 2 Gale: {com_gale2}
❌ Perdas reais: {perdas}
    """
    bot.reply_to(message, placar)

print("🤖 Bac Bo Signal Bot Iniciado!")
threading.Thread(target=monitorar, daemon=True).start()
bot.infinity_polling()
