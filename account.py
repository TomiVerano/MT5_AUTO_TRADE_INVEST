from _pydatetime import timedelta

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, time as dtime
import pytz
import numpy as np
from config import *
from profit_utils import *
import time
SOFIA_TZ = pytz.timezone("Europe/Sofia")


class Account:
    ACCOUNTS = []

    def __init__(self, name, login, password, server):
        self.name = name
        self.login = login
        self.password = password
        self.server = server
        self.connected = False
        self.open_orders = []
        self.pending_orders = []
        self.ban_swap = []
        self.delay_orders = []
        Account.ACCOUNTS.append(self)

    # -------------------- MARKET WAIT HELPERS --------------------
    def _wait_until(self, target_dt):
        """Sleep until target datetime in Sofia timezone."""
        while True:
            now = datetime.now(SOFIA_TZ)
            if now >= target_dt:
                break
            seconds = (target_dt - now).total_seconds()
            print(f"{self.name}: ⏳ Waiting {int(seconds // 60)} min...")
            time.sleep(min(seconds, 60))

    def handle_market_close(self):
        """Check if market is closed → wait until market available."""
        now = datetime.now(SOFIA_TZ)
        weekday = now.weekday()     # Monday=0 ... Sunday=6
        current_time = now.time()

        # Weekend
        if weekday >= 5:   # Saturday(5) / Sunday(6)
            print(f"{self.name}: Market closed (Weekend). Waiting until Monday 00:10...")
            days_until_monday = (7 - weekday) % 7
            monday = now + timedelta(days=days_until_monday)
            target_dt = monday.replace(hour=0, minute=10, second=0, microsecond=0)
            self._wait_until(target_dt)
            return

        # Weekday before 12:00
        if current_time < dtime(12, 0):
            print(f"{self.name}: Market not active before 12:00. Waiting 15 minutes...")
            target_dt = now + timedelta(minutes=15)
            self._wait_until(target_dt)
            return

        print(f"{self.name}: Market assumed active.")
        return

    # -------------------- CONNECTION --------------------
    def connect(self):
        # First try initialize
        if not mt5.initialize():
            print(f"{self.name}: ❌ MT5 init failed:", mt5.last_error())
            self.handle_market_close()

            # Retry after waiting
            if not mt5.initialize():
                print(f"{self.name}: ❌ Retry MT5 init failed:", mt5.last_error())
                return False

        # Try login
        if not mt5.login(self.login, password=self.password, server=self.server):
            print(f"{self.name}: ❌ Login failed:", mt5.last_error())
            self.handle_market_close()

            # Retry after waiting
            if not mt5.login(self.login, password=self.password, server=self.server):
                print(f"{self.name}: ❌ Retry login failed:", mt5.last_error())
                return False

        self.connected = True
        print(f"{self.name}: ✅ Connected successfully.")
        return True

    # -------------------- MARGIN CHECK (NOT TESTED) --------------------
    def can_open_position(self, symbol=None, lot=0.01):
        """
        Check if the account has enough equity and margin to safely open a new position.
        Optionally checks symbol-specific required margin if symbol and lot are provided.
        """
        info = mt5.account_info()
        if info is None:
            print(f"{self.name}: ❌ Failed to get account info")
            return False

        equity = info.equity
        margin = info.margin
        free_margin = info.margin_free

        # --- Handle stop-out data safely ---
        stop_out_mode = getattr(info, "margin_so_mode", 0)

        stop_out_level = getattr(info, "margin_so_so", 0.0)  # stop-out level in %

        # --- Compute minimum equity requirement ---
        if stop_out_mode == 0:  # percent-based
            stop_out_equity = margin * (stop_out_level / 100.0)
        else:  # money or margin-based
            stop_out_equity = stop_out_level

        safety_buffer = 50.0  # EUR/USD equivalent buffer
        min_equity_required = stop_out_equity + safety_buffer

        if equity <= min_equity_required:
            print(
                f"{self.name}: ⚠️ Trade blocked: too close to stop-out! "
                f"Equity={equity:.2f}, Required>={min_equity_required:.2f}"
            )
            return False

        # --- Optional: symbol-specific margin check ---
        if symbol and lot > 0:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                print(f"{self.name}: ⚠️ Cannot get tick for {symbol}")
                return False

            order_type = mt5.ORDER_TYPE_BUY  # margin same for buy/sell
            try:
                required_margin = mt5.order_calc_margin(order_type, symbol, lot, tick.ask)
            except Exception as e:
                print(f"{self.name}: ⚠️ Failed to calculate margin for {symbol}: {e}")
                return False

            if free_margin < required_margin:
                print(
                    f"{self.name}: ⚠️ Not enough free margin for {symbol} | "
                    f"Required={required_margin:.2f}, Free={free_margin:.2f}"
                )
                return False

        return True

    # -------------------- STATIC: CHECK IF SYMBOL IS TRADABLE --------------------
    # feature off need fix and testing
    # @staticmethod
    # def is_tradable_now_static(symbol: str, account_currency: str = "USD") -> bool:
    #
    #     # SOFIA_TZ = pytz.timezone("Europe/Sofia")
    #     now_sofia = datetime.now(SOFIA_TZ)
    #     current_time = now_sofia.time()
    #
    #     symbol = symbol.upper()
    #     if len(symbol) < 6:
    #         return False
    #     base = symbol[:3]
    #
    #     # Define trading windows per base currency (Sofia time)
    #     windows_map = {
    #         "EUR": [(dtime(15, 15), dtime(18, 45))],
    #         "GBP": [(dtime(15, 15), dtime(18, 45))],
    #         "USD": [(dtime(15, 15), dtime(18, 45))],
    #         "JPY": [(dtime(3, 15), dtime(11, 45)), (dtime(15, 15), dtime(18, 45))],
    #         "AUD": [(dtime(1, 15), dtime(4, 45))],
    #         "NZD": [(dtime(1, 15), dtime(4, 45))],
    #         "CAD": [(dtime(15, 15), dtime(23, 44))],
    #         "CHF": [(dtime(15, 15), dtime(18, 45))],
    #         "CNH": [(dtime(3, 15), dtime(11, 45))],
    #         "NOK": [(dtime(15, 15), dtime(22, 45))],
    #         "SEK": [(dtime(15, 15), dtime(22, 45))],
    #         "ZAR": [(dtime(15, 15), dtime(22, 45))],
    #         "MXN": [(dtime(15, 15), dtime(22, 45))],
    #     }
    #
    #     # Optional: refine by account currency if needed
    #     trading_windows = windows_map
    #     windows = trading_windows.get(base)
    #     if not windows:
    #         return False
    #
    #     # Check if current Sofia time falls into any window
    #     return any(start <= current_time <= end for start, end in windows)

    # -------------------- FINDS CURRENT ACCOUNT INFO --------------------

    @staticmethod
    def get_account_info():
        acc_info = mt5.account_info()
        if acc_info is None:
            return {}

        info = {}
        for field in dir(acc_info):
            if not field.startswith("_"):
                value = getattr(acc_info, field)
                if not callable(value):
                    info[field] = value

        return info

    @staticmethod
    def get_forex_pairs(money_type: str):
        symbols = mt5.symbols_get()
        if not symbols:
            return []
        return [s.name for s in symbols if money_type.upper() in s.name]

    # -------------------- CALCULATING PROFIT --------------------
    @staticmethod
    def calc_virtual_profit(vo: dict, account_currency) -> dict:
        """
        Calculate current virtual profit for a given order.
        Returns both profit in pips and in base account currency (USD/EUR).
        Automatically handles pip scaling and JPY pairs.
        """

        symbol = vo.get("symbol")
        if not symbol:
            return {"profit_pips": 0, f"profit_{account_currency.lower()}": 0}

        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if not info or not tick:
            return {"profit_pips": 0, f"profit_{account_currency.lower()}": 0}

        entry_price = vo.get("entry_price", tick.bid)
        signal = vo.get("signal", "").lower()
        order_type = 0 if signal == "buy" else 1
        volume = vo.get("volume", 0.1)

        # --- Pip & point calculation ---
        pip = 0.0001 if "JPY" not in symbol else 0.01

        # --- Current price depending on order type ---
        current_price = tick.bid if order_type == 1 else tick.ask

        # --- Calculate profit in pips ---
        if order_type == 0:  # Buy
            profit_pips = (current_price - entry_price) / pip
        else:  # Sell
            profit_pips = (entry_price - current_price) / pip

        # --- Convert pips to profit in account currency ---
        # Approx pip value = $10 per standard lot (1.0)
        profit_usd = profit_pips * (10 * volume)

        # --- If account is EUR, convert approx USD→EUR using EURUSD quote ---
        if account_currency.upper() == "EUR":
            eurusd = mt5.symbol_info_tick("EURUSD")
            if eurusd and eurusd.bid > 0:
                profit_currency = profit_usd / eurusd.bid
            else:
                profit_currency = profit_usd * 0.92  # fallback conversion
        else:
            profit_currency = profit_usd

        return {
            "profit_pips": round(profit_pips, 2),
            f"profit_{account_currency.lower()}": round(profit_currency, 2)
        }

    # -------------------- CREATE A SIGNAL BUY SELL NONE --------------------
    @staticmethod
    def get_data(symbol, timeframe=mt5.TIMEFRAME_M5, period_fast=8, period_slow=21):

        """
        Create signal here.
        Returns:
            "buy"  -> fast EMA > slow EMA
            "sell" -> fast EMA < slow EMA
            None   -> not enough data or no signal
        """
        now_sofia = pd.Timestamp.now(tz=SOFIA_TZ)
        end_utc = now_sofia.tz_convert("UTC")

        # Load ~300 bars to compute EMAs well
        rates = mt5.copy_rates_from(symbol, timeframe, end_utc.to_pydatetime(), 300)
        if rates is None or len(rates) < period_slow + 2:
            return None  # not enough data

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)

        # Calculate EMAs
        df['ema_fast'] = df['close'].ewm(span=period_fast).mean()
        df['ema_slow'] = df['close'].ewm(span=period_slow).mean()

        # Last candle
        last = df.iloc[-1]

        if last['ema_fast'] > last['ema_slow']:
            return "buy"

        elif last['ema_fast'] < last['ema_slow']:
            return "sell"

        else:
            return None

    # -------------------- PRINT PENDING ORDERS NOT IN OPEN --------------------
    def print_pending_not_in_open(self):
        """
        Prints details of pending orders that do NOT exist in open_orders.
        """
        open_symbols = {o["symbol"] for o in self.open_orders}

        pending_only = [p for p in self.pending_orders if p["symbol"] not in open_symbols]

        if not pending_only:
            print(f"{self.name}: ✅ No pending orders outside open_orders.")
            return

        print(f"{self.name}: 🔹 Pending orders not in open_orders: {len(pending_only)}")
        for p in pending_only:
            print(f"Pending order | Symbol: {p['symbol']} | Ticket: {p.get('ticket')} | "
                  f"Signal: {p['signal']} | Volume: {p['volume']} | Virtual: {p['virtual']}")
        print("-" * 60)

    # -------------------- COMPARE OPEN & PENDING ORDERS --------------------
    def compare_open_pending_orders(self):
        """
        Loops through open_orders and pending_orders.
        If a symbol exists in both, print details side by side.
        """
        # Build dicts for quick lookup by symbol
        open_dict = {o["symbol"]: o for o in self.open_orders}
        pending_dict = {p["symbol"]: p for p in self.pending_orders}

        # Check intersection
        common_symbols = set(open_dict.keys()) & set(pending_dict.keys())

        if not common_symbols:
            print(f"{self.name}: ℹ️ No common symbols found in open_orders and pending_orders.")
            return

        print(f"{self.name}: 🔍 Comparing open_orders vs pending_orders for {len(common_symbols)} common symbols:")

        for symbol in common_symbols:
            o = open_dict[symbol]
            p = pending_dict[symbol]

            print(f"1. Open order  | Symbol: {o['symbol']} | Ticket: {o.get('ticket')} | "
                  f"Signal: {o['signal']} | Volume: {o['volume']} | Virtual: {o['virtual']}")
            print(f"2. Pending order | Symbol: {p['symbol']} | Ticket: {p.get('ticket')} | "
                  f"Signal: {p['signal']} | Volume: {p['volume']} | Virtual: {p['virtual']}")
            print("-" * 60)

    # -------------------- MODIFY TRADE PAIR ACCOUNTS --------------------
    def get_exotic_pairs(self):
        mapping = {
            "USD": {"USDZAR", "USDMXN", "USDSEK", "USDNOK"},
            "EUR": {"EURDKK", "EURHKD", "EURSGD", "EURTRY"},
            # Add other account currencies if needed
        }
        return mapping.get(self.get_account_info().get("currency").upper(), set())

    # -------------------- HELPER: AUTODETECT FILL MODE --------------------
    @staticmethod
    def _get_fill_mode(symbol):
        """Try to detect allowed fill mode (FOK or IOC) for given symbol."""
        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                return mt5.ORDER_FILLING_FOK  # fallback
            # filling_mode is a bitmask; check for supported flags
            if info.filling_mode & mt5.ORDER_FILLING_FOK:
                return mt5.ORDER_FILLING_FOK
            elif info.filling_mode & mt5.ORDER_FILLING_IOC:
                return mt5.ORDER_FILLING_IOC
            else:
                return mt5.ORDER_FILLING_FOK  # default fallback
        except (mt5.MT5Error, TypeError, ValueError) as e:
            print("Order error:", e)
            return mt5.ORDER_FILLING_FOK  # default fallback

    # -------------------- CREATE VIRTUAL ORDER --------------------
    def create_virtual_order(self, symbol, signal, lot=VOL_ST):
        """Create a virtual order with proper SL/TP distances and broker safety adjustments."""
        tick = mt5.symbol_info_tick(symbol)
        info = mt5.symbol_info(symbol)
        if not tick or not info:
            print(f"{self.name}: ⚠️ Missing tick or symbol info for {symbol}")
            return None

        # --- Constants and base configuration ---
        ep = self.get_exotic_pairs()
        pip = info.point
        digits = info.digits
        spread = (tick.ask - tick.bid)
        stop_level = info.trade_stops_level * pip  # broker min distance for SL/TP

        # --- Distance settings (wider for exotic pairs) ---
        base_distance = FIX_MARGIN_REAL * pip
        if symbol in ep:
            base_distance *= VOL_MULT_FACTOR * 4.0  # buffer for high volatility

        real_distance = max(base_distance, stop_level * 2)
        virt_distance = real_distance / 2

        # --- Price levels based on direction ---
        if signal.lower() == "buy":
            virt_tp = round(tick.ask + virt_distance, digits)
            virt_sl = round(tick.bid - virt_distance, digits)
            real_tp = round(tick.ask + real_distance, digits)
            real_sl = round(tick.bid - real_distance, digits)
            order_type = mt5.ORDER_TYPE_BUY
        else:
            virt_tp = round(tick.bid - virt_distance, digits)
            virt_sl = round(tick.ask + virt_distance, digits)
            real_tp = round(tick.bid - real_distance, digits)
            real_sl = round(tick.ask + real_distance, digits)
            order_type = mt5.ORDER_TYPE_SELL

        # --- SL/TP validation (avoid Invalid Stops) ---
        min_distance_ok = (abs(real_tp - tick.ask) > stop_level) and (abs(tick.bid - real_sl) > stop_level)
        if not min_distance_ok:
            adjust = stop_level * 1.2
            if signal.lower() == "buy":
                real_tp = round(tick.ask + adjust, digits)
                real_sl = round(tick.bid - adjust, digits)
            else:
                real_tp = round(tick.bid - adjust, digits)
                real_sl = round(tick.ask + adjust, digits)
            print(f"{self.name}: ⚙️ Adjusted SL/TP for {symbol} to avoid invalid stops")

        # --- Compose virtual order dict ---
        vo = {
            "ticket": f"VIRTUAL_{symbol}_{pd.Timestamp.now().floor('s')}",
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "signal": signal.lower(),
            "virtual_tp": virt_tp,
            "virtual_sl": virt_sl,
            "real_tp": real_tp,
            "real_sl": real_sl,
            "spread": round(spread, digits),
            "linked_real_order": None,
            "virtual": True,
            "time": pd.Timestamp.now(),
            "fill_mode": self._get_fill_mode(symbol),
        }

        print(
            f"{self.name}: ✅ Virtual order created -> {symbol} | Signal: {signal.upper()} "
            f"| Spread: {vo['spread']:.{digits}f} | Fill mode: {vo['fill_mode']} | "
            f"Real SL/TP adjusted OK"
        )

        return vo

    # -------------------- CLOSE REAL ORDER (robust: ticket OR symbol) --------------------
    def close_real_order(self, ticket=None, symbol=None, max_retries=6, wait_between=0.7):
        pos = None
        if ticket:
            pos_list = mt5.positions_get(ticket=ticket)
            if pos_list:
                pos = pos_list[0]
            else:
                print(f"{self.name}: ℹ️ close_real_order: no position found for ticket {ticket}")

        if pos is None and symbol:
            pos_list = mt5.positions_get(symbol=symbol)
            if pos_list:
                pos = pos_list[0]
                print(f"{self.name}: ℹ️ close_real_order: found position ticket {pos.ticket} for {symbol}")

        if pos is None:
            print(f"{self.name}: ⚠️ close_real_order: no open position found (ticket={ticket}, symbol={symbol})")
            return False

        try:
            if pos.type == mt5.POSITION_TYPE_BUY:
                close_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(pos.symbol).bid
            else:
                close_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(pos.symbol).ask
        except Exception as e:
            print(f"{self.name}: ⚠️ close_real_order: error determining price/type: {e}")
            return False

        fill_mode = self._get_fill_mode(pos.symbol)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 100,
            "magic": 123456,
            "comment": f"{self.name} close {pos.symbol}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": fill_mode,
        }

        for attempt in range(1, max_retries + 1):
            result = mt5.order_send(request)
            if result is None:
                print(f"{self.name}: ❌ order_send() returned None (attempt {attempt})")
            else:
                print(
                    f"{self.name}: ℹ️ close order_send retcode={getattr(result, 'retcode', None)}, comment={getattr(result, 'comment', None)}")

                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    for _ in range(8):
                        time.sleep(0.25)
                        if not mt5.positions_get(ticket=pos.ticket):
                            print(f"{self.name}: 🧾 Closed real order {pos.ticket} ({pos.symbol}) confirmed.")
                            self._cleanup_closed_position(pos.symbol, pos.ticket)
                            return True
                #elif result.retcode in [mt5.TRADE_RETCODE_INVALID_FILL, mt5.TRADE_RETCODE_INVALID_PARAMS]:
                elif result.retcode in [mt5.TRADE_RETCODE_INVALID_FILL]:
                    # retry with alternate mode
                    alt_mode = mt5.ORDER_FILLING_IOC if fill_mode == mt5.ORDER_FILLING_FOK else mt5.ORDER_FILLING_FOK
                    print(f"{self.name}: 🔄 Retrying with alternate fill mode: {alt_mode}")
                    request["type_filling"] = alt_mode
                    result = mt5.order_send(request)
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        print(f"{self.name}: ✅ Closed with alternate fill mode ({alt_mode}).")
                        self._cleanup_closed_position(pos.symbol, pos.ticket)
                        return True

            time.sleep(wait_between)

        print(f"{self.name}: ⛔ Failed to close {pos.symbol} after {max_retries} attempts")
        return False

    # -------------------- CLEANUP HELPER --------------------
    def _cleanup_closed_position(self, symbol: str, ticket: int = None):
        """
        Removes closed position from self.open_orders/open_positions and ban_positions.
        Called automatically after confirmed close.
        """
        # --- remove from open_orders / open_positions ---
        if hasattr(self, "open_orders"):
            before = len(self.open_orders)
            self.open_orders = [
                o for o in self.open_orders
                if o.get("symbol") != symbol and o.get("linked_real_order") != ticket
            ]
            after = len(self.open_orders)
            if before != after:
                print(f"{self.name}: 🧹 Removed {symbol} from open_orders (ticket={ticket}).")

        # --- remove from pending_orders ---
        if hasattr(self, "pending_orders"):
            before = len(self.pending_orders)
            self.pending_orders = [
                o for o in self.pending_orders
                if o.get("symbol") != symbol
            ]
            after = len(self.pending_orders)
            if before != after:
                print(f"{self.name}: 🧹 Removed {symbol} from pending_orders")

        # --- remove from ban_positions if present ---
        if symbol in getattr(self, "ban_positions", {}):
            del self.ban_positions[symbol]
            print(f"{self.name}: 🚫 Unbanned {symbol} (closed position).")

    # -------------------- EXECUTE REAL ORDER (robust linking) --------------------
    def execute_virtual_order(self, vo):
        symbol = vo["symbol"]
        lot = vo["volume"]
        order_type = vo["type"]
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            print(f"{self.name}: ⚠️ No tick for {symbol}")
            return None

        price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid
        fill_mode = vo.get("fill_mode", self._get_fill_mode(symbol))

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": vo.get("real_sl"),
            "tp": vo.get("real_tp"),
            "deviation": 50,
            "magic": 123456,
            "comment": f"{self.name} executed {vo['signal']}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": fill_mode,
        }

        result = mt5.order_send(request)
        if result is None:
            print(f"{self.name}: ❌ order_send() returned None for executing {symbol}")
            return None

        if result.retcode == mt5.TRADE_RETCODE_INVALID_FILL:
            # try alternative mode
            alt_mode = mt5.ORDER_FILLING_IOC if fill_mode == mt5.ORDER_FILLING_FOK else mt5.ORDER_FILLING_FOK
            print(f"{self.name}: 🔄 Retrying execute {symbol} with alternate fill mode {alt_mode}")
            request["type_filling"] = alt_mode
            result = mt5.order_send(request)

        print(
            f"{self.name}: ℹ️ execute order result -> retcode={getattr(result, 'retcode', None)}, order={getattr(result, 'order', None)}, comment={getattr(result, 'comment', None)}")

        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            print(
                f"{self.name}: ⚠️ Failed to execute real order for {symbol}: retcode={result.retcode}, comment={result.comment}")
            return None

        # confirm linking
        real_ticket = None
        for _ in range(8):
            pos_list = mt5.positions_get(symbol=symbol)
            if pos_list:
                for p in pos_list:
                    if abs(p.volume - lot) < 1e-6:
                        real_ticket = p.ticket
                        break
                if real_ticket:
                    break
            time.sleep(0.4)

        if real_ticket:
            vo["linked_real_order"] = real_ticket
            vo["virtual"] = False
            print(
                f"{self.name}: 🧾 Real order executed for {symbol} [{vo['signal'].upper()}] → position ticket {real_ticket}")
        else:
            print(f"{self.name}: ⚠️ Could not confirm linked real position for {symbol}")

        return result

    # -------------------- COLLECT, SORT & BAN POSITIONS --------------------
    def collect_positions(self):
        """
        Fetch all open positions, calculate profit, classify them,
        create matching virtual orders, and update open_orders & ban_positions.
        Skips symbols that are banned, already in open_orders, or in pending_orders.
        """
        if not self.connected:
            print(f"{self.name}: ⚠️ Not connected. Call .connect() first.")
            return

        positions = mt5.positions_get()
        if positions is None:
            print(f"{self.name}: ⚠️ No positions found or MT5 error ->", mt5.last_error())
            return

        acc_info = self.get_account_info()
        account_currency = acc_info.get("currency").upper()

        all_positions = []

        for pos in positions:
            symbol = pos.symbol
            signal = "buy" if pos.type == mt5.ORDER_TYPE_BUY else "sell"

            # --- skip if symbol is banned, already in open_orders, or pending_orders ---
            if symbol in self.ban_positions:
                continue
            if any(o["symbol"] == symbol for o in self.open_orders):
                continue
            if any(o["symbol"] == symbol for o in getattr(self, "pending_orders", [])):
                continue

            # Get tick/info
            info = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            if not info or not tick:
                print(f"{self.name}: ⚠️ Missing tick/info for {symbol}")
                continue

            lot = pos.volume

            # --- fetch TP/SL from MT5 position ---
            real_tp = pos.tp
            real_sl = pos.sl

            # --- calculate virtual TP/SL as half distance from entry ---
            if signal.lower() == "buy":
                virt_tp = pos.price_open + (
                            real_tp - pos.price_open) / 2 if real_tp != 0 else pos.price_open + FIX_MARGIN_REAL * info.point
                virt_sl = pos.price_open - (
                            pos.price_open - real_sl) / 2 if real_sl != 0 else pos.price_open - FIX_MARGIN_REAL * info.point
                order_type = mt5.ORDER_TYPE_BUY
            else:
                virt_tp = pos.price_open - (
                            pos.price_open - real_tp) / 2 if real_tp != 0 else pos.price_open - FIX_MARGIN_REAL * info.point
                virt_sl = pos.price_open + (
                            real_sl - pos.price_open) / 2 if real_sl != 0 else pos.price_open + FIX_MARGIN_REAL * info.point
                order_type = mt5.ORDER_TYPE_SELL

            # --- unified VO structure ---
            vo = {
                "ticket": pos.ticket,
                "symbol": symbol,
                "volume": lot,
                "type": order_type,
                "signal": signal,
                "entry_price": pos.price_open,
                "virtual_tp": round(virt_tp, info.digits),
                "virtual_sl": round(virt_sl, info.digits),
                "real_tp": round(real_tp, info.digits) if real_tp else None,
                "real_sl": round(real_sl, info.digits) if real_sl else None,
                "linked_real_order": pos.ticket,
                "virtual": False,
                "time": pd.Timestamp.fromtimestamp(pos.time),
            }

            # --- create virtual order if not already in open_orders ---
            virt_order = self.create_virtual_order(symbol, signal, lot=lot)
            if virt_order:
                # Check if ticket already exists
                if any(o["ticket"] == virt_order["ticket"] for o in self.open_orders):
                    continue
                vo["linked_virtual_order"] = virt_order

            # --- append to open_orders and ban_positions ---
            self.open_orders.append(vo)
            self.ban_positions[symbol] = signal

            all_positions.append(vo)

        print(
            f"{self.name}: ✅ Positions collected: {len(all_positions)} | "
            # f"Positive: {len(self.positive)} / Negative: {len(self.negative)} | "
            f"Open orders: {len(self.open_orders)} | Account currency: {account_currency}"
        )

    # -------------------- INITIALIZE PENDING VIRTUAL ORDERS --------------------
    def initialize_pending_orders(self):
        """
        Initialize virtual orders for all tradable symbols that are not banned
        or already in open orders. Store them in self.pending_orders.
        """
        if not self.connected:
            print(f"{self.name}: ⚠️ Not connected. Call .connect() first.")
            return

        # --- Get account currency automatically ---
        acc_info = self.get_account_info()
        currency = acc_info.get("currency").upper()

        # --- Keywords to exclude anywhere in the symbol ---
        exclude_keywords = ("TRY","INDEX", "XAU", "XPT", "XPD", "XAG", "BTC", "ETH", "LTC", "XRP", "BCH", "DASH", "SOL", "UNI", "LINK", "ADA", "DOT", "DOGE", "ZEC", "XLM", "ETC", "ADA", "DOT", "DOGE", "ZEC", "XLM")

        # --- Get tradable symbols for account currency ---
        forex_pairs_account = self.get_forex_pairs(currency)

        # --- Filter symbols: exclude if keyword appears anywhere in symbol ---
        filtered_symbols = [
            s for s in forex_pairs_account
            if not any(keyword in s.upper() for keyword in exclude_keywords)
        ]

        print(f"{self.name}: Account currency = {currency}, tradable symbols count = {len(filtered_symbols)}")

        print(f"{self.name}: 🔍 Initializing virtual orders for {len(filtered_symbols)} symbols...")

        if not hasattr(self, "pending_orders"):
            self.pending_orders = []

        for pair in filtered_symbols:
            # Skip if symbol is banned or already in open_orders
            # if pair in self.ban_positions:
            #     continue
            # if any(o["symbol"] == pair for o in self.open_orders):
            #     continue
            if any(o["symbol"] == pair for o in self.pending_orders):
                continue

            # Check symbol info
            info = mt5.symbol_info(pair)
            if not info or info.trade_mode != mt5.SYMBOL_TRADE_MODE_FULL:
                continue

            # Get signal for pair (you already have get_data())
            sig = self.get_data(pair)
            if not sig:
                continue

            # Create virtual order
            vo = self.create_virtual_order(pair, sig)
            if vo:
                self.pending_orders.append(vo)

        print(f"{self.name}: ✅ Pending orders initialized: {len(self.pending_orders)}")

    # -------------------- EXECUTE PENDING VIRTUAL ORDERS --------------------
    def execute_pending_orders(self):
        """
        Execute virtual orders from pending_orders if the symbol is currently tradable.
        If the signal has changed, update the virtual order using full TP/SL and execute it.
        Moves executed orders to open_orders and updates ban_positions.
        """
        if not self.connected:
            print(f"{self.name}: ⚠️ Not connected. Call .connect() first.")
            return

        if not hasattr(self, "pending_orders") or not self.pending_orders:
            print(f"{self.name}: ⚠️ No pending orders to execute.")
            return

        executed_count = 0
        remaining_pending = []

        for vo in self.pending_orders:
            symbol = vo["symbol"]

            # --- Skip if swap-banned ---
            if symbol in getattr(self, "ban_swap", []):
                print(f"{self.name}: 🚫 {symbol} is swap-banned. Skipping pending order.")
                remaining_pending.append(vo)
                continue

            # --- Check if symbol is currently tradable --- 0ff
            # if not Account.is_tradable_now_static(symbol, account_currency=acc_currency):
            #     remaining_pending.append(vo)
            #     continue

            # --- Margin safety check before executing ---
            if not self.can_open_position():
                print(f"{self.name}: ⚠️ Not enough margin to open {symbol}.")
                remaining_pending.append(vo)
                continue

            # --- Get current market signal ---
            current_signal = self.get_data(symbol)
            if not current_signal:
                remaining_pending.append(vo)
                continue

            # --- Update virtual order if signal changed and move to delay orders ---
            if current_signal is None:
                continue
            if vo["signal"].lower() != current_signal.lower() and vo["symbol"] not in self.delay_orders:
                new_vo = self.create_virtual_order(symbol, current_signal, lot=vo["volume"])
                if new_vo:
                    # --- Close existing real positions ---
                    pos_list = mt5.positions_get(symbol=symbol)
                    if pos_list:
                        for pos in pos_list:
                            print(
                                f"{self.name}: ⚙️ Closing existing position {pos.ticket} for {symbol} before executing new VO")
                            close_result = self.close_real_order(ticket=pos.ticket, symbol=symbol)
                            if close_result:
                                now = pd.Timestamp.now()

                                new_vo["comment"] = f"DELAY-REUSE {now.strftime('%Y-%m-%d %H:%M:%S')}"
                                new_vo["time_created"] = now
                                new_vo["time_execute"] = now + pd.Timedelta(minutes=9)

                                self.delay_orders.append(new_vo)

                                print(f"{self.name}: ⏳ VO scheduled for {symbol}, executes after 9 min.")

                                vo["signal"] = current_signal
                                self.open_orders.append(new_vo)

            if any(o["symbol"] == symbol for o in self.open_orders):
                remaining_pending.append(vo)
                continue
            else:
                if vo["symbol"] not in self.delay_orders:
                    result = self.execute_virtual_order(vo)
                    if result:
                        self.open_orders.append(vo)

        # Update pending_orders with remaining (not yet executed)
        self.pending_orders = remaining_pending

        print(f"{self.name}: ✅ Executed {executed_count} virtual orders, {len(self.pending_orders)} still pending.")

    # -------------------- MONITOR VIRTUAL ORDERS --------------------
    def monitor_virtual_orders(self):

        """
        Monitors all open virtual orders:
        - Displays current price, P/L, TP, SL
        - Detects TP/SL hits
        - Closes TP/SL hits
        """

        if not self.open_orders:
            return

        account_currency = self.get_account_info().get("currency").upper()

        for vo in list(self.open_orders):
            symbol = vo["symbol"]
            info = mt5.symbol_info(symbol)
            tick = mt5.symbol_info_tick(symbol)
            if not tick or not info:
                continue

            signal = vo["signal"]
            order_type = vo["type"]
            virt_tp, virt_sl = vo["virtual_tp"], vo["virtual_sl"]
            current_price = tick.ask if order_type == mt5.ORDER_TYPE_BUY else tick.bid

            # --- Check TP / SL hits ---
            hit_tp = current_price > virt_tp if signal == "buy" else current_price < virt_tp
            hit_sl = current_price < virt_sl if signal == "buy" else current_price > virt_sl

            # --- Calculate current virtual profit ---
            profit_data = self.calc_virtual_profit(vo, account_currency)
            vo.update(profit_data)

            print(f"{self.name}: 🔁 {symbol} {signal.upper()} | "
                  f"P/L: {profit_data[f'profit_{account_currency.lower()}']:+.2f} "
                  f"({profit_data['profit_pips']:+.1f} pips) | "
                  f"Virt TP: {virt_tp:.5f} | SL: {virt_sl:.5f}")

            # --- Handle TP / SL hit events ---
            if hit_tp or hit_sl:
                hit_type = "TP" if hit_tp else "SL"
                print(f"{self.name}: 🎯 {symbol} → Virtual {hit_type} hit! Closing and reversing...")

                if vo.get("linked_real_order"):
                    old_ticket = vo["linked_real_order"]
                    pos_info = mt5.positions_get(ticket=old_ticket)
                    if pos_info:
                        pos = pos_info[0]
                        print(
                            f"{self.name}: ⚙️ Attempting to close old real position for {symbol} (ticket {pos.ticket})")
                        closed_ok = self.close_real_order(ticket=pos.ticket, symbol=pos.symbol)

                        if not closed_ok:
                            print(
                                f"{self.name}: ⚠️ Failed to close old position for {symbol} (ticket {pos.ticket})")

    # -------------------- MONITOR NEGATIVE SWAP --------------------
    def apply_swap_to_orders(self):
        """
        Evaluates swap impact for all open orders based on account currency (EUR/USD).
        - Negative swap & positive profit → close order and ban symbol
        - Negative swap & non-profitable → keep open
        - Positive swap → keep open
        """
        if not hasattr(self, "ban_swap"):
            self.ban_swap = []

        acc_info = self.get_account_info()
        account_currency = acc_info.get("currency").upper()

        for vo in list(self.open_orders):
            symbol = vo["symbol"]
            signal = vo["signal"]
            info = mt5.symbol_info(symbol)
            if not info:
                continue

            # --- Determine swap value ---
            swap_value = info.swap_long if signal == "buy" else info.swap_short

            # --- Adjust slightly for cross currency base ---
            if "USD" not in symbol and account_currency == "USD":
                swap_value /= 1.1
            elif "EUR" not in symbol and account_currency == "EUR":
                swap_value /= 1.1

            # --- Compute current profit ---
            profit_data = self.calc_virtual_profit(vo, account_currency)
            current_profit = profit_data.get(f"profit_{account_currency.lower()}", 0)

            # === CASE 1: Negative swap, profitable → CLOSE + BAN ===
            if swap_value < 0 < current_profit:
                print(
                    f"{self.name}: ⚠️ {symbol} has NEGATIVE swap ({swap_value:.2f}) and PROFIT {current_profit:+.2f} → closing before rollover.")

                closed = False
                if vo.get("linked_real_order"):
                    pos_info = mt5.positions_get(ticket=vo["linked_real_order"])
                    if pos_info:
                        pos = pos_info[0]
                        closed = self.close_real_order(ticket=pos.ticket, symbol=pos.symbol)
                else:
                    closed = self.close_real_order(symbol=symbol)

                if closed:
                    print(f"{self.name}: 💰 Closed {symbol} (locked profit, neg. swap). Added to ban_swap.")
                    if symbol not in self.ban_swap:
                        self.ban_swap.append(symbol)
                    self.open_orders.remove(vo)
                continue

            # === CASE 2: Negative swap, not profitable → KEEP ===
            if swap_value < 0 and current_profit <= 0:
                print(
                    f"{self.name}: 💤 {symbol} has NEGATIVE swap ({swap_value:.2f}) but still losing ({current_profit:+.2f}) → keeping open.")
                continue

            # === CASE 3: Positive swap → KEEP ===
            if swap_value > 0:
                print(f"{self.name}: ✅ {symbol} has POSITIVE swap ({swap_value:.2f}) → keeping open.")
                continue

        print(
            f"{self.name}: 📋 Swap check complete — {len(self.ban_swap)} symbols banned due to negative swap with profit.")

    # -------------------- APPLY CLOSE TO ORDERS WITH NEGATIVE SWAP --------------------
    def manage_daily_swap_updates(self):
        """
        Checks current Sofia time:
        - At 23:40 → run apply_swap_to_orders()
        - Every day at 00:16 → clear self.ban_swap
        """
        now = datetime.now(SOFIA_TZ)
        current_time = now.time()

        # --- Ensure ban_swap exists ---
        if not hasattr(self, "ban_swap"):
            self.ban_swap = []

        # --- Daily 23:40 swap refresh ---
        if dtime(23, 40) <= current_time <= dtime(23, 45):
            print(f"{self.name}: ⏰ 23:40 Sofia — applying daily swap updates.")
            self.apply_swap_to_orders()

        # --- Daily reset around midnight ---
        if dtime(0, 16) <= current_time <= dtime(0, 20):
            if self.ban_swap:
                print(f"{self.name}: 🔄 {now.strftime('%A %H:%M')} — clearing {len(self.ban_swap)} swap-banned symbols.")
                self.ban_swap.clear()
            else:
                print(f"{self.name}: 🧹 {now.strftime('%A %H:%M')} — ban_swap already empty.")

    # -------------------- EXECUTE DELAY ORDERS --------------------
    def execute_delay_orders(self):
        now_sofia = datetime.now(SOFIA_TZ)

        ready = [vo for vo in self.delay_orders if now_sofia >= vo["time_execute"]]

        for vo in ready:
            symbol = vo["symbol"]
            print(f"{self.name}: 🚀 Executing delayed VO for {symbol}")

            result = self.execute_virtual_order(vo)

            if result:
                self.open_orders.append(vo)
                # self.ban_positions[symbol] = vo["signal"]

            self.delay_orders = [o for o in self.delay_orders if o is not vo]






