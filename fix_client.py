import quickfix as fix
import random
import time
import os
from datetime import datetime
import pytz

class SequenceManager:
    def __init__(self, filename="sequence.txt"):
        self.filename = filename
        self.current_seq = self.load_sequence()

    def load_sequence(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                return int(f.read().strip())
        return 1

    def save_sequence(self):
        with open(self.filename, 'w') as f:
            f.write(str(self.current_seq))

    def get_next_sequence(self):
        self.current_seq += 1
        self.save_sequence()
        return self.current_seq

    def set_sequence(self, seq):
        self.current_seq = seq
        self.save_sequence()

    def reset_sequence(self):
        self.set_sequence(1)
        
class Order:
    def __init__(self, clOrdID, symbol, side, quantity, price=None):
        self.clOrdID = clOrdID
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.executions = []

    def add_execution(self, lastShares, lastPx):
        self.executions.append((lastShares, lastPx))

    def calculate_vwap(self):
        total_qty = sum(exec[0] for exec in self.executions)
        total_px_qty = sum(exec[0] * exec[1] for exec in self.executions)
        return total_px_qty / total_qty if total_qty else 0

class FIXClient(fix.Application):
    def __init__(self):
        super().__init__()
        self.seq_manager = SequenceManager()
        self.session_id = None
        self.orders = {}
        self.total_volume = 0.0
        self.pnl = 0.0
        self.vwap = {}
        self.expected_seq = None

    def reset_sequence_if_needed(self):
        sgt = pytz.timezone("Asia/Singapore")
        current_time_sgt = datetime.now(sgt)
        reset_time_sgt = current_time_sgt.replace(hour=0, minute=0, second=0, microsecond=0)

        if current_time_sgt >= reset_time_sgt:
            print("Resetting sequence number due to daily reset.")
            self.seq_manager.set_sequence(1)

    def onCreate(self, sessionID):
        self.session_id = sessionID
        self.reset_sequence_if_needed()
        print(f"Session created: {sessionID}")

    def onLogon(self, sessionID):
        print(f"Logon - {sessionID}")

    def onLogout(self, sessionID):
        print(f"Logout - {sessionID}")

    def toAdmin(self, message, sessionID):
        # No custom handling required
        pass

    def toApp(self, message, sessionID):
        # No custom handling required
        pass

    def fromAdmin(self, message, sessionID):
        msgType = fix.MsgType()
        message.getHeader().getField(msgType)
        if msgType.getValue() == fix.MsgType_Reject:
            refSeqNum = fix.RefSeqNum()
            message.getField(refSeqNum)
            print(f"Received Reject for message {refSeqNum.getValue()}")

            text = fix.Text()
            if message.isSetField(text):
                message.getField(text)
                if "MsgSeqNum too low" in text.getValue():
                    expected_seq = int(text.getValue().split("expecting")[1].split()[0])
                    self.handle_sequence_reset(expected_seq)

    def fromApp(self, message, sessionID):
        print("Received Message: ", message)
        msg_type = fix.MsgType()
        message.getHeader().getField(msg_type)

        if msg_type.getValue() == fix.MsgType_ExecutionReport:
            self.process_execution_report(message)
        elif msg_type.getValue() == fix.MsgType_OrderCancelReject:
            self.process_cancel_reject(message)
        elif msg_type.getValue() == fix.MsgType_Reject:
            print("Order Rejected: ", message)

    def send_order(self, symbol, side, order_type):
        orderID = str(random.randint(1, 100000))
        quantity = random.randint(10, 100)
        message = fix.Message()
        header = message.getHeader()

        header.setField(fix.BeginString(fix.BeginString_FIX42))
        header.setField(fix.MsgType(fix.MsgType_NewOrderSingle))
        header.setField(fix.SenderCompID("OPS_CANDIDATE_3_8639"))
        header.setField(fix.TargetCompID("DTL"))

        next_seq = self.seq_manager.get_next_sequence()
        header.setField(fix.MsgSeqNum(next_seq))
        print(f"Sending order with sequence number: {next_seq}")

        message.setField(fix.ClOrdID(orderID))
        message.setField(fix.HandlInst('1'))
        message.setField(fix.Symbol(symbol))
        message.setField(fix.Side(side))
        message.setField(fix.OrdType(order_type))
        message.setField(fix.OrderQty(quantity))

        if order_type == fix.OrdType_LIMIT:
            price = random.uniform(100, 150)
            message.setField(fix.Price(price))
        else:
            price = None

        fix.Session.sendToTarget(message, self.session_id)

        # Store order data for statistics calculation
        order = Order(orderID, symbol, side, quantity, price)
        self.orders[orderID] = order

        return orderID  # Return order ID for potential cancellation

    def process_execution_report(self, message):
        exec_type = fix.ExecType()
        message.getField(exec_type)

        clOrdID = fix.ClOrdID()
        message.getField(clOrdID)

        symbol = fix.Symbol()
        message.getField(symbol)

        lastShares = fix.LastShares()
        message.getField(lastShares)

        lastPx = fix.LastPx()
        message.getField(lastPx)

        if exec_type.getValue() == fix.ExecType_FILL:
            order = self.orders.get(clOrdID.getValue())
            if order:
                order.add_execution(lastShares.getValue(), lastPx.getValue())

                self.total_volume += lastShares.getValue() * lastPx.getValue()
                if order.side == fix.Side_BUY:
                    self.pnl -= lastShares.getValue() * lastPx.getValue()
                else:
                    self.pnl += lastShares.getValue() * lastPx.getValue()

                if symbol.getValue() not in self.vwap:
                    self.vwap[symbol.getValue()] = {'total_price_qty': 0, 'total_qty': 0}
                self.vwap[symbol.getValue()]['total_price_qty'] += lastShares.getValue() * lastPx.getValue()
                self.vwap[symbol.getValue()]['total_qty'] += lastShares.getValue()

    def process_cancel_reject(self, message):
        print("Order Cancel Rejected: ", message)

    def calculate_stats(self):
        print(f"Total Trading Volume: ${self.total_volume:.2f}")
        print(f"PNL: ${self.pnl:.2f}")
        for symbol, data in self.vwap.items():
            vwap = data['total_price_qty'] / data['total_qty']
            print(f"VWAP for {symbol}: ${vwap:.2f}")

    def handle_sequence_reset(self, expected_seq):
        print(f"Handling sequence reset. Expected: {expected_seq}")
        self.seq_manager.set_sequence(expected_seq - 1)  # Set to one less to allow increment
        next_seq = self.seq_manager.get_next_sequence()
        fix.Session.setNextSenderMsgSeqNum(next_seq)
        print(f"Sequence number reset to: {next_seq}")

    def cancel_order(self, orig_order_id):
        cancel_id = str(random.randint(1, 100000))
        message = fix.Message()
        header = message.getHeader()

        header.setField(fix.BeginString(fix.BeginString_FIX42))
        header.setField(fix.MsgType(fix.MsgType_OrderCancelRequest))
        header.setField(fix.SenderCompID("OPS_CANDIDATE_3_8639"))
        header.setField(fix.TargetCompID("DTL"))

        next_seq = self.seq_manager.get_next_sequence()
        header.setField(fix.MsgSeqNum(next_seq))
        print(f"Sending cancel request with sequence number: {next_seq}")

        message.setField(fix.ClOrdID(cancel_id))
        message.setField(fix.OrigClOrdID(orig_order_id))
        message.setField(fix.Symbol(self.orders[orig_order_id].symbol))
        message.setField(fix.Side(self.orders[orig_order_id].side))
        message.setField(fix.OrderQty(self.orders[orig_order_id].quantity))

        fix.Session.sendToTarget(message, self.session_id)

        # Remove order from local tracking
        if orig_order_id in self.orders:
            del self.orders[orig_order_id]


if __name__ == "__main__":
    settings = fix.SessionSettings('fix.cfg')
    application = FIXClient()

    storeFactory = fix.FileStoreFactory(settings)
    logFactory = fix.FileLogFactory(settings)
    initiator = fix.SocketInitiator(application, storeFactory, settings, logFactory)
    initiator.start()

    # Wait for the session to be established
    while application.session_id is None:
        time.sleep(1)

    # Sending random orders
    symbols = ["MSFT", "AAPL", "BAC"]
    sides = [fix.Side_BUY, fix.Side_SELL, fix.Side_SELL]
    order_types = [fix.OrdType_LIMIT, fix.OrdType_MARKET]

    order_ids = []

    for _ in range(1000):
        symbol = random.choice(symbols)
        side = random.choice(sides)
        order_type = random.choice(order_types)
        order_id = application.send_order(symbol, side, order_type)
        order_ids.append(order_id)
        time.sleep(0.3)

        # Randomly cancel orders
        if random.random() < 0.1 and order_ids:  # 10% chance to cancel an order
            cancel_id = random.choice(order_ids)
            application.cancel_order(cancel_id)
            order_ids.remove(cancel_id)

    # Wait for a bit to allow for order processing
    time.sleep(60)

    application.calculate_stats()
    initiator.stop()
