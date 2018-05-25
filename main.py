import numpy as np
import talib
import requests
import time
import os

url_candles = 'http://everyday.com.ng/api/candles/?coin={}&ticks=100&length={}'
url_coins = 'http://everyday.com.ng/api/coins/'
OVERBOUGHT = 'Overbought'
OVERSOLD = 'Oversold'
NEUTRAL = 'Neutral'
UPTREND = 'Possible Up Trend'
DOWNTREND = 'Possible Down Trend'
STRONG = 'Strong'
BUY = 'Buy'
SELL = 'Sell'
BULL_CROSS = 'Bullish Crossover'
BEAR_CROSS = 'Bearish Crossover'
BEARISH_DIVERGENCE = 'Bearish Divergence'
BULLISH_DIVERGENCE = 'Bullish Divergence'
ADX_MAP = {}
TICK_LENGTH = 30  # 30-min candles


def send_message(text):
    chat_id = os.environ['CHAT_ID']
    _url = os.environ['TELEGRAM_URL'].format(os.environ['TELEGRAM_TOKEN'])
    endpoint = 'sendMessage?parse_mode=HTML&text={}&chat_id={}'.format(text, chat_id)
    url = _url + endpoint
    requests.get(url)


def get_data(coin):
    resp = requests.get(url_candles.format(coin, TICK_LENGTH))
    candles = resp.json()['candles']
    inputs = {
        'open': np.array([i['open'] for i in candles]),
        'close': np.array([i['close'] for i in candles]),
        'high': np.array([i['high'] for i in candles]),
        'low': np.array([i['low'] for i in candles]),
        'volume': np.array([i['volume'] for i in candles])
    }
    return inputs


def stochastic(inputs):
    signals = []
    slowk, slowd = talib.STOCH(
        inputs['high'], inputs['low'], inputs['close'], 8, 3, 0, 3, 0)
    if slowk[-1] > 80 and slowd[-1] > 80:
        signals.append(OVERBOUGHT)
    elif slowk[-1] < 20 and slowd[-1] < 20:
        signals.append(OVERSOLD)

    # check if k-line is above d-line and it is growing
    if slowk[-1] > slowd[-1] and slowk[-1] > slowk[-2]:
        signals.append(BUY)
    if slowd[-1] > slowk[-1] and slowk[-1] < slowk[-2]:
        signals.append(SELL)
    if slowk[-2] < slowd[-2] and slowk[-1] > slowd[-1]:
        signals.append(BULL_CROSS)
    if slowk[-2] > slowd[-2] and slowk[-1] < slowd[-1]:
        signals.append(BEAR_CROSS)
    #    if not OVERBOUGHT in signals:
    #        signals.append(BUY)
    return signals


def adx(inputs):
    #signals = []
    _adx = talib.ADX(inputs['high'], inputs['low'], inputs['close'])
    return _adx[-1]
    #if _adx[-1] > 50:
    #    signals.append(STRONG)
    #return signals


def rsi(inputs):
    signals = []
    res = talib.RSI(inputs['close'])[-1]
    if res > 70:
        signals.append(OVERBOUGHT)
    elif res < 30:
        signals.append(OVERSOLD)
    elif res > 50:
        signals.append(UPTREND)
    else:
        signals.append(DOWNTREND)
    return signals


def macd(inputs):
    signals = []
    price_highs = np.argpartition(inputs['high'][-50:], -2)[-2:]
    price_lows = np.argpartition(inputs['low'][-50:], 2)[:2]

    _macd, _signal, _hist = talib.MACD(inputs['close'])

    macd_highs = np.argpartition(_macd[-50:], -2)[-2:]
    macd_lows = np.argpartition(_macd[-50:], 2)[:2]

    if price_highs[0] < price_highs[1]:
        # higher highs
        if macd_highs[0] > macd_highs[1]:
            signals.append(BEARISH_DIVERGENCE)
    if price_lows[0] > price_lows[1]:
        # lower lows
        if macd_lows[0] < macd_lows[1]:
            signals.append(BULLISH_DIVERGENCE)

    # macd line growing indicates buy
    if _hist[-1] > _hist[-2] > _hist[-3]:
        signals.append(BUY)
    if _hist[-1] < _hist[-2] < _hist[-3]:
        signals.append(SELL)
    # macd bullish and bearish cross-overs
    if _macd[-1] > _signal[-1] and _macd[-2] <= _signal[-2]:
        signals.append(BULL_CROSS)
    if _macd[-1] < _signal[-1] and _macd[-2] >= _signal[-2]:
        signals.append(BEAR_CROSS)
    return signals


def get_coins():
    resp = requests.get(url_coins).json()
    return resp['coins'], resp['watch']


def strip(coin):
    return coin.split('_')[1]


def start(coins):
    results = {
        'stochastic': {OVERBOUGHT: [], OVERSOLD: [], BUY: [], SELL: [], BULL_CROSS: [], BEAR_CROSS: []},
        'rsi': {OVERBOUGHT: [], OVERSOLD: [], UPTREND: [], DOWNTREND: []},
        'adx': {STRONG: []},
        'macd': {BUY: [], SELL: [], BULLISH_DIVERGENCE: [], BEARISH_DIVERGENCE: [], BULL_CROSS: [], BEAR_CROSS: []},
        'st_macd': {BUY: [], SELL: []}
    }
    for coin in coins:
        time.sleep(2)

        try:
            inputs = get_data(coin)
        except Exception:
            continue
        for stoch in stochastic(inputs):
            results['stochastic'][stoch].append(strip(coin))
        #for _adx in adx(inputs):
        #    results['adx'][_adx].append(strip(coin))
        for _rsi in rsi(inputs):
            results['rsi'][_rsi].append(strip(coin))
        for _macd in macd(inputs):
            results['macd'][_macd].append(strip(coin))
        _adx = adx(inputs)
        ADX_MAP.update({strip(coin): _adx})
        if _adx >= 30:
            results['adx'][STRONG].append(strip(coin))

    return results


def by_strength(coins):
    '''Arrange coins by ADX value.'''
    _weighted = [(coin, ADX_MAP.get(coin)) for coin in coins]
    _weighted.sort(key=lambda x: x[1], reverse=True)
    return [i[0] for i in _weighted]


if __name__ == '__main__':
    from pprint import pprint
    import sys
    if len(sys.argv) == 1:
        coins, watches = get_coins()
    else:
        coins = [sys.argv[1]]
        watches = []
    res = start(coins)
    pprint(ADX_MAP)

    text_list = ['Report from indicators']
    _oversold = by_strength(res['stochastic'][OVERSOLD])
    if _oversold:
        text_list.append('STOCH Oversold: ' + ', '.join(_oversold))

    _overbought = [i for i in res['stochastic'][OVERBOUGHT] if i in watches]
    if _overbought:
        text_list.append('STOCH Overbought: ' + ', '.join(_overbought))

    _cross = by_strength(res['stochastic'][BUY])
    if _cross:
        text_list.append('STOCH Crossovers: ' + ', '.join(_cross))

    #text_list.append('RSI Oversold: ' + ', '.join(res['rsi'][OVERSOLD]))
    _adx = by_strength(res['adx'][STRONG])
    if _adx:
        text_list.append('Strong ADX: ' + ', '.join(_adx))

    _macd_buy = by_strength(res['macd'][BUY])
    if _macd_buy:
        text_list.append('MACD Buy: ' + ', '.join(_macd_buy))

    _macd_sell = [i for i in res['macd'][SELL] if i in watches]
    if _macd_sell:
        text_list.append('MACD Sell: ' + ', '.join(_macd_sell))

    text_list.append('Bullish Divergence signals: ' + ', '.join(res['macd'][BULLISH_DIVERGENCE]))
    text_list.append('Bearish Divergence signals: ' + ', '.join(res['macd'][BEARISH_DIVERGENCE]))

    _rec = set(res['stochastic'][BUY]).intersection(res['macd'][BUY]).intersection(res['stochastic'][OVERSOLD]).intersection(res['adx'][STRONG])
    rec = by_strength(_rec)
    if rec:
        recommended = ', '.join(i for i in rec)
        text_list.append('Recommended Buys: {}'.format(recommended))
    _bull_cross_s = set(res['stochastic'][BULL_CROSS]).intersection(res['macd'][BUY])
    _bull_cross_m = set(res['macd'][BULL_CROSS]).intersection(res['stochastic'][BUY])
    _bull_cross = _bull_cross_s.union(_bull_cross_m)
    if _bull_cross:
        bc = ', '.join(i for i in _bull_cross)
        text_list.append('Bull Crossovers: {}'.format(bc))
    _bear_cross = res['stochastic'][BEAR_CROSS] + res['macd'][BEAR_CROSS]
    if _bear_cross:
        beer = ', '.join(i for i in _bear_cross)
        text_list.append('Bear Crossovers: {}'.format(beer))

    text = '\n'.join(text_list)
    send_message(text)

    #res = start()
    #pprint(res)
    #print(res)
