# MT5_AUTO_TRADE_INVEST
MT5 python pandas numpy automatic algo trade multi-signal multi-asset multi-broker trading

© 2025 Anton Vatkov  
Licensed under CC BY-NC 4.0  
You may use, modify, and share this work for non-commercial purposes with attribution.
This project is provided for personal and educational use only.  
Commercial use is strictly prohibited without explicit written permission.

📌 Design Note: Built to extend over the official MT5 Python integration.
Docs: https://www.mql5.com/en/docs/python_metatrader5

### 🏗 Architecture Diagram — MT5 Virtual + Real Order System

```mermaid
graph TD
    cfg[config.py] --> ACC[Account Class]
    ACC --> CONN[Connection Layer\nconnect()\nhandle_market_close()]
    ACC --> STATE[Trading State\nopen_orders[]\npending_orders[]\ndelay_orders[]\nban_swap[]\nban_positions{}]
    ACC --> UTIL[Utilities\nget_account_info()\nget_data()\ncalc_virtual_profit()]
    ACC --> VPIPE[Virtual Order Pipeline\ninit_pending_orders()\ncreate_virtual_order()]
    VPIPE --> PENDING[pending orders]
    PENDING --> OPEN[open_orders]
    ACC --> REAL[Real Order Layer\nexecute_virtual_order()\nclose_real_order()\ncleanup_closed()]
    REAL --> MT5API[MT5 Python API]

# 🔄 Auto-Trading System (MT5 + Python)

> Fully automated FX trading using MetaTrader 5 + Python
> Author: **Anton Vatkov**
> Licensed under **CC BY-NC 4.0**

---

## ✅ What This Does (Simple Explanation)

This program connects to a broker through **MetaTrader 5 (MT5)** and performs automated trading based on signals you define.

✔ Reads broker account & available tradable pairs
✔ Creates virtual orders in memory
✔ Converts them into real trades
✔ Monitors price + TP/SL
✔ If the signal changes → closes the position and creates the opposite order
✔ Opposite trades wait **9 minutes** before activating

This enables automatic algorithmic trading with controlled execution and minimal user work.

---

## ✅ Features

| Feature                         | Description                                     |
| ------------------------------- | ----------------------------------------------- |
| ✅ Auto connect                  | Logs into MT5 broker                            |
| ✅ Multi-account rotation        | Trades sequentially across accounts             |
| ✅ Virtual orders                | Internal state management before real execution |
| ✅ Executing real trades         | Converts VO → real positions                    |
| ✅ Signal-based logic            | BUY / SELL / NONE                               |
| ✅ 9-min delay after signal flip | Reduces noise                                   |
| ✅ Internal TP/SL                | Logical profit & loss management                |
| ✅ Per-symbol management         | No cross-pair conflict                          |
| ✅ Beginner friendly             | Simple, customizable code                       |

---

## ✅ 1) Installation

### Requirements

| Component | Version        |
| --------- | -------------- |
| Python    | 3.10+          |
| MT5       | Windows client |
| pandas    | Latest         |
| pytz      | Latest         |

### Install

```bash
pip install MetaTrader5 pandas pytz
```

---

## ✅ 2) MT5 Setup

1. Install and open MetaTrader 5
2. Log in to your broker
3. Enable Algo Trading:
   ✅ Tools → Options → Expert Advisors → Allow automated trading
4. Keep MT5 running

---

## ✅ 3) Configure Accounts

In `runner.py`:

```python
ACCOUNTS = [
    Account("Benchmark_USD", 4443331, "PASSWORD", "BenchMark-Server"),
    Account("Benchmark_EUR", 4443332, "PASSWORD", "BenchMark-Server"),
]
```

---

## ✅ 4) How The System Trades

### Step-By-Step

1. Connect to MT5
2. Detect available tradable pairs
3. Get trading signal via:

   ```
   Account.get_data(symbol)
   ```
4. If signal returns "buy" or "sell" → create a **virtual order**
5. Virtual order is added to pending queue
6. If still valid → real trade executed
7. If signal reverses:

   * Close the current trade
   * Create new opposite-direction virtual order
   * Wait **9 minutes**
   * Then allow activation
8. Check internal TP/SL values
9. Repeat forever

---

## ✅ 5) Simple EMA Signal Example

```python
def get_data(self, symbol):
    prices = self.get_rates(symbol, period=5)
    if prices is None or len(prices) < 21:
        return None

    ema_fast = prices.ewm(span=8).mean().iloc[-1]
    ema_slow = prices.ewm(span=21).mean().iloc[-1]

    if ema_fast > ema_slow:
        return "buy"
    elif ema_fast < ema_slow:
        return "sell"
    return None
```

---

## ✅ 7) Delay Orders

If the signal changes direction:

* Current trade closes
* A reverse VO is created
* VO waits **9 minutes** before activation
* Helps filter noise + fast signal flips

---

## ✅ 9) Run

```bash
python runner.py
```

---

## ✅ 10) Recommended Usage

✅ Use demo first
✅ Modify signal logic
✅ Adjust volumes + pairs + swaps etc. (pre build for forex only)
✅ Monitor logs

---

## ✅ Disclaimer

This software can execute real trades.
Use responsibly and at your own risk.
No performance guarantees.

---

# ✅ License

```
© 2025 Anton Vatkov  
Licensed under CC BY-NC 4.0  

You may use, modify, and share this work for non-commercial purposes
with attribution.

This project is provided for personal and educational use only.
Commercial use is strictly prohibited without explicit written permission.
```
