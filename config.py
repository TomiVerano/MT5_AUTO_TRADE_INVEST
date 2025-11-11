# Global settings
# ------------------ EMA SETTINGS ------------------
FAST = 8       # EMA fast period
SLOW = 21      # EMA slow period

# ------------------ FIXED DISTANCES ------------------
FIX_MARGIN_REAL = 360     # Real TP/SL distance in pips
# FIX_MARGIN_VIRT = 40      # Virtual TP/SL distance in pips

# ------------------ SL / TP ADJUSTMENTS ------------------
# SL_SHIFT_PIPS = 3         # Pips to shift SL on reversal
# TP_MULTIPLIER = 1.5       # Multiply TP distance on reversal
# VOLUME_MULTIPLIER = 3     # Multiply lot size on reversal

# ------------------ DEFAULT LOTS ------------------
VOL_ST = 0.01       # Default lot size

# ------------------ PROFIT REVERSAL ------------------
# PROFIT_THRESHOLD = -2.2   # If virtual order loses this profit, trigger reversal
# REVERSAL_LOT_MULTIPLIER = 3  # Multiply lot on reversal after loss

# ------------------ TIME SETTINGS ------------------
MONITOR_INTERVAL = 3      # Seconds between virtual order checks
SAVE_INTERVAL = 60        # Seconds between saving account state

# ------------------ EXOTIC PAIRS ------------------
# EXOTIC_PAIRS = {"USDZAR", "USDMXN", "USDSEK", "USDNOK"}

# ------------------ MISC ------------------
VOL_MULT_FACTOR = 40      # Factor to adjust distance for exotic pairs

# VOL_ST = 0.01
# FIX_MARGIN_VIRT = 200   # Virtual order TP/SL points
# FIX_MARGIN_REAL = 300   # Real order TP/SL points
# FAST = 8
# SLOW = 21
# # ------------------ VIRTUAL SL REVERSAL ------------------
# SL_SHIFT_PIPS = 60  # how many pips to shift SL when hit
# TP_MULTIPLIER = 2  # how many times to extend TP distance
# VOLUME_MULTIPLIER = 2  # how many times to increase volume