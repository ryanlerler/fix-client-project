# FIX Client Application

This application simulates sending and receiving orders using the FIX protocol. It includes sequence number management, order tracking, and PnL (Profit and Loss) calculation.

## Design Overview

The application is built using the `quickfix` library on Python 3.11.5. It manages sequence numbers, sends orders, handles execution reports, and calculates statistics like VWAP and PnL.

### Key Components
- **SequenceManager:** Manages sequence numbers, ensuring they reset daily.
- **Order:** Represents an order with its attributes and execution details.
- **FIXClient:** Handles FIX session management, order processing, and statistics calculation.

## How to Run

1. Ensure `quickfix` is installed:
   ```bash
   pip install quickfix

2. python3 fix_client.py
