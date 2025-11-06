import time
import MetaTrader5 as mt5
from account import Account

# Time to stay logged into each account (in seconds)
ACCOUNT_SESSION_TIME = 40

# Wait between full rotations
ROTATION_PAUSE = 3  # seconds between accounts

# Example accounts — replace with your real credentials
# Example accounts — replace with your real credentials
ACCOUNTS = [
    Account("BROCKERNAME", 1112223, "password", "brockerName-Server"),
    Account("BROCKERNAME1", 1112224, "password", "brockerName-Server1"),
]

def process_account(acc: Account):
    print(f"\n🔐 Connecting to {acc.name} ({acc.login})...")
    if not acc.connect():
        print(f"{acc.name}: ❌ Connection failed.")
        return

    # Load saved orders before running
    # load_account_state(acc)

    # Start trading session
    print(f"{acc.name}: ▶️ Starting trading cycle...")
    start_time = time.time()

    try:
        # acc.session_init()  # initial virtual orders if needed
        while time.time() - start_time < ACCOUNT_SESSION_TIME:
            acc.manage_daily_swap_updates()
            acc.collect_positions()
            acc.initialize_pending_orders()
            acc.execute_pending_orders()
            acc.monitor_virtual_orders()
            acc.compare_open_pending_orders()
            acc.print_pending_not_in_open()
            acc.execute_delay_orders()
            time.sleep(3)  # monitor every 3 seconds
    except Exception as e:
        print(f"{acc.name}: ⚠️ Error during session -> {e}")

    # Save and logout
    # save_account_state(acc)
    mt5.shutdown()
    acc.connected = False
    print(f"{acc.name}: 🔒 Logged out.\n")
    time.sleep(ROTATION_PAUSE)


def main():
    print(f"🚀 Starting account rotation ({len(ACCOUNTS)} accounts)...")
    while True:
        for acc in ACCOUNTS:
            process_account(acc)
        print("🔁 Completed full rotation — restarting...\n")
        time.sleep(5)


if __name__ == "__main__":
    main()
