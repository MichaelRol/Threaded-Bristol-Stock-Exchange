import sys
import random
from BSE2_msg_classes import Assignment, Order, ExchMsg


# #################--Traders below here--#############


# Trader superclass
# all Traders have a trader id, bank balance, blotter, and list of orders to execute
class Trader:

    def __init__(self, ttype, tid, balance, time):
        self.ttype = ttype  # what type / strategy this trader is
        self.tid = tid  # trader unique ID code
        self.lei = 'NoLEI'   # Legal Entity Identifier for the entity that owns/operates this trader
        self.balance = balance  # money in the bank
        self.blotter = []  # record of trades executed
        self.orders = []  # customer orders currently being worked
        self.max_cust_orders = 1  # maximum number of distinct customer orders allowed at any one time.
        self.quotes = []  # distinct quotes currently live on the LOB
        self.max_quotes = 1  # maximum number of distinct quotes allowed on LOB
        self.willing = 1  # used in ZIP etc
        self.able = 1  # used in ZIP etc
        self.birthtime = time  # used when calculating age of a trader/strategy
        self.profitpertime = 0  # profit per unit time
        self.n_trades = 0  # how many trades has this trader done?
        self.lastquote = None  # record of what its most recent quote was/is (incl price)
        self.paramvec = []  # vector of parameter values -- stored separately for switching between strategies

    def __str__(self):
        blotterstring = '['
        for b in self.blotter:
            blotterstring = blotterstring + '[[%s], %s]' % (str(b[0]), b[1])
        blotterstring = blotterstring + ']'
        return '[TID=%s(%s) type=%s $=%s blotter=%s orders=%s n_trades=%s profitpertime=%s]' \
               % (self.tid, self.lei, self.ttype, self.balance, blotterstring, self.orders, self.n_trades, self.profitpertime)

    # add a customer order (i.e., an "assignment") to trader's records
    def add_cust_order(self, order, verbose):
        # currently LAZY: keeps to within max_cust_orders by appending new order and deleting head self.orders
        if len(self.quotes) > 0:
            # this trader has a live quote on the LOB, from a previous customer order
            # need response to signal cancellation/withdrawal of that quote
            response = 'LOB_Cancel'
        else:
            response = 'Proceed'
        if len(self.orders) >= self.max_cust_orders:
            self.orders = self.orders[1:]
        self.orders.append(order)
        if verbose:
            print('add_order < response=%s self.orders=%s' % (response, str(self.orders)))
        return response

    # delete a customer order from trader's list of orders being worked
    def del_cust_order(self, cust_order_id, verbose):
        if verbose:
            print('>del_cust_order: Cust_orderID=%s; self.orders=' % cust_order_id)
            for o in self.orders:
                print('%s ' % str(o))

        cust_orders = []
        for co in self.orders:
            if co.assignmentid != cust_order_id:
                cust_orders.append(co)

        self.orders = cust_orders

    # revise a customer order: used after a PARTial fill on the exchange
    def revise_cust_order(self, cust_order_id, revised_order, verbose):
        if verbose:
            print('>revise_cust_order: Cust_orderID=%s; revised_order=%s, self.orders=' %
                  (cust_order_id, revised_order))
            for o in self.orders:
                print('%s ' % str(o))

        cust_orders = []
        for co in self.orders:
            if co.assignmentid != cust_order_id:
                cust_orders.append(co)
            else:
                revised_assignment = co
                revised_assignment.qty = revised_order.qty
                cust_orders.append(revised_assignment)

        self.orders = cust_orders

        if verbose:
            print('<revise_cust_order: Cust_orderID=%s; revised_order=%s, self.orders=' %
                  (cust_order_id, revised_order))
            for o in self.orders:
                print('%s ' % str(o))

    # delete an order/quote from the trader's list of its orders live on the exchange
    def del_exch_order(self, oid, verbose):
        if verbose:
            print('>del_exch_order: OID:%d; self.quotes=' % oid)
            for q in self.quotes:
                print('%s ' % str(q))

        exch_orders = []
        for eo in self.quotes:
            if eo.orderid != oid:
                exch_orders.append(eo)

        self.quotes = exch_orders

    # bookkeep(): trader book-keeping in response to message from the exchange
    def bookkeep(self, msg, time, verbose):
        # update records of what orders are still being worked, account balance, etc.
        # trader's blotter is sequential record of each exchange-message received, + trader's balance after that msg

        if verbose:
            print('>bookkeep msg=%s bal=%d' % (msg, self.balance))

        profit = 0

        if msg.event == "CAN":
            # order was cancelled at the exchange
            # so delete the order from the trader's records of what quotes it has live on the exchange
            if verbose:
                print(">CANcellation: msg=%s quotes=" % str(msg))
                for q in self.quotes:
                    print("%s" % str(q))

            newquotes = []
            for q in self.quotes:
                if q.orderid != msg.oid:
                    newquotes.append(q)
            self.quotes = newquotes

            if verbose:
                print("<CANcellation: quotes=")
                for q in self.quotes:
                    print("%s" % str(q))

        # an individual order of some types (e.g. MKT) can fill via transactions at different prices
        # so the message that comes back from the exchange has transaction data in a list: will often be length=1

        if msg.event == "FILL" or msg.event == "PART":

            for trans in msg.trns:
                transactionprice = trans["Price"]
                qty = trans["Qty"]

                # find this LOB order in the trader's list of quotes sent to exchange
                exch_order = None
                for order in self.quotes:
                    if order.orderid == msg.oid:
                        exch_order = order
                    break
                if exch_order is None:
                    s = 'FAIL: bookkeep() cant find order (msg.oid=%d) orders=' % msg.oid
                    for order in self.quotes:
                        s = s + str(order)
                    sys.exit(s)

                limitprice = exch_order.price

                if exch_order.otype == 'Bid':
                    profit = (limitprice - transactionprice) * qty
                else:
                    profit = (transactionprice - limitprice) * qty

                self.balance += profit
                self.n_trades += 1
                age = time - self.birthtime
                self.profitpertime = self.balance / age

                if verbose:
                    print('Price=%d Limit=%d Q=%d Profit=%d N_trades=%d Age=%f Balance=%d' %
                          (transactionprice, limitprice, qty, profit, self.n_trades, age, self.balance))

                if profit < 0:
                    print(self.tid)
                    print(self.ttype)
                    print(profit)
                    print(exch_order)
                    sys.exit('Exit: Negative profit')

            if verbose:
                print('%s: profit=%d bal=%d profit/time=%f' %
                      (self.tid, profit, self.balance, self.profitpertime))

            # by the time we get to here, exch_order is instantiated
            cust_order_id = exch_order.myref

            if msg.event == "FILL":
                # this order has completed in full, so it thereby completes the corresponding customer order
                # so delete both the customer order from trader's record of those
                # and the order has already been deleted from the exchange's records, so ...
                # ... also needs to be deleted from trader's records of orders held at exchange
                cust_order_id = exch_order.myref
                if verbose:
                    print('>bookkeep() deleting customer order ID=%s' % cust_order_id)
                self.del_cust_order(cust_order_id, verbose)  # delete this customer order
                if verbose:
                    print(">bookkeep() deleting OID:%d from trader's exchange-order records" % exch_order.orderid)
                self.del_exch_order(exch_order.orderid, verbose)  # delete the exchange-order from trader's records

            elif msg.event == "PART":
                # the customer order is still live, but its quantity needs updating
                if verbose:
                    print('>bookkeep() PART-filled order updating qty on customer order ID=%s' % cust_order_id)
                self.revise_cust_order(cust_order_id, msg.revo, verbose)  # delete this customer order

                if exch_order.ostyle == "IOC":
                    # a partially filled IOC has the non-filled portion cancelled at the exchange,
                    # so the trader's order records need to be updated accordingly
                    if verbose:
                        print("PART-filled IOC cancels remainder: deleting OID:%d from trader's exchange-order records"
                              % exch_order.orderid)
                    self.del_exch_order(exch_order.orderid, verbose)  # delete the exchange-order from trader's records

        self.blotter.append([msg, self.balance])  # add trade record to trader's blotter

    # specify how trader responds to events in the market
    # this is a null action, expect it to be overloaded by specific algos
    def respond(self, time, lob, trade, verbose):
        if verbose:
            print('>Mutate: %s %s %s' % (time, lob, trade))
        return None

    # specify how trader mutates its parameter values
    # this is a null action, expect it to be overloaded by specific algos
    def mutate(self, time, lob, trade, verbose):
        if verbose:
            print('>Mutate: %s %s %s' % (time, lob, trade))
        return None


# Trader subclass Giveaway
# even dumber than a ZI-U: just give the deal away
# (but never makes a loss)
class Trader_Giveaway(Trader):

    def getorder(self, time, countdown, lob, verbose):

        if verbose:
            print('GVWY getorder:')

        if len(self.orders) < 1:
            order = None
        else:
            quoteprice = self.orders[0].price
            order = Order(self.tid,
                          self.orders[0].atype,
                          self.orders[0].astyle,
                          quoteprice,
                          self.orders[0].qty,
                          time, None, -1)
            self.lastquote = order
        return order


# Trader subclass ZI-C
# After Gode & Sunder 1993
class Trader_ZIC(Trader):

    def getorder(self, time, countdown, lob, verbose):

        if verbose:
            print('ZIC getorder:')

        if len(self.orders) < 1:
            # no orders: return NULL
            order = None
        else:
            minprice = lob['bids']['worstp']
            maxprice = lob['asks']['worstp']

            limit = self.orders[0].price
            otype = self.orders[0].atype
            ostyle = self.orders[0].astyle
            if otype == 'Bid':
                oprice = random.randint(minprice, limit)
            else:
                oprice = random.randint(limit, maxprice)
                # NB should check it == 'Ask' and barf if not
            order = Order(self.tid, otype, ostyle, oprice, self.orders[0].qty, time, None, -1)
            self.lastquote = order
        return order


# Trader subclass Shaver
# shaves a penny off the best price
class Trader_Shaver(Trader):

    def getorder(self, time, countdown, lob, verbose):

        if verbose:
            print("SHVR getorder:")

        if len(self.orders) < 1:
            order = None
        else:
            if verbose:
                print(" self.orders[0]=%s" % str(self.orders[0]))
            limitprice = self.orders[0].price
            otype = self.orders[0].atype
            ostyle = self.orders[0].astyle
            if otype == 'Bid':
                if lob['bids']['n'] > 0:
                    quoteprice = lob['bids']['bestp'] + 1
                    if quoteprice > limitprice:
                        quoteprice = limitprice
                else:
                    quoteprice = lob['bids']['worstp']
            else:
                if lob['asks']['n'] > 0:
                    quoteprice = lob['asks']['bestp'] - 1
                    if quoteprice < limitprice:
                        quoteprice = limitprice
                else:
                    quoteprice = lob['asks']['worstp']
            order = Order(self.tid, otype, ostyle, quoteprice, self.orders[0].qty, time, None, -1)
            self.lastquote = order
        return order


# Trader subclass Imbalance-sensitive Shaver
# shaves X off the best price, where X depends on supply/demand imbalance
class Trader_ISHV(Trader):

    def __init__(self, ttype, tid, balance, time):
        # the init params are all here to make explicit what the user has to specify for ISHV
        Trader.__init__(self, ttype, tid, balance, time)
        self.shave_c = 2         # c in the y=mx+c linear mapping from imbalance to shave amount
        self.shave_m = 1         # m in the y=mx+c
        self.shave_min = 1       # minimum shave
        self.price_nobids = 1    # price quoted if there are no bids to shave up from
        self.price_noasks = 200  # price quoted if there are no asks to shave down from

    def getorder(self, time, countdown, lob, verbose):

        if verbose:
            print("ISHV getorder:")

        if len(self.orders) < 1:
            order = None
        else:
            if verbose:
                print(" self.orders[0]=%s" % str(self.orders[0]))
            limitprice = self.orders[0].price
            otype = self.orders[0].atype
            ostyle = self.orders[0].astyle

            microp = lob['microprice']
            midp = lob['midprice']

            if microp is not None and midp is not None:
                imbalance = microp - midp
            else:
                imbalance = 0  # if imbalance is undefined, proceed as if it is equal to zero

            if otype == 'Bid':

                # quantity sensitivity
                if imbalance < 0:
                    shaving = self.shave_min  # imbalance in favour of buyers, so shave slowly
                else:
                    shaving = self.shave_c + (self.shave_m * int(imbalance * 100) / 100)  # shave ever larger amounts

                print('t:%f, ISHV (Bid) imbalance=%s shaving=%s' % (time, imbalance, shaving))

                if len(lob['bids']['lob']) > 0:
                    quoteprice = lob['bids']['bestp'] + shaving
                    if quoteprice > limitprice:
                        quoteprice = limitprice
                else:
                    quoteprice = self.price_nobids
            else:
                # quantity sensitivity
                if imbalance > 0:
                    shaving = self.shave_min
                else:
                    shaving = self.shave_c - (self.shave_m * int(imbalance * 100) / 100)

                print('t:%f, ISHV (Ask) imbalance=%s shaving=%s' % (time, imbalance, shaving))

                if len(lob['asks']['lob']) > 0:
                    quoteprice = lob['asks']['bestp'] - shaving
                    if quoteprice < limitprice:
                        quoteprice = limitprice
                else:
                    quoteprice = self.price_noasks

            order = Order(self.tid, otype, ostyle, quoteprice, self.orders[0].qty, time, None, verbose)
            self.lastquote = order

        return order


# Trader subclass Sniper
# Based on Shaver, inspired by Kaplan
# "lurks" until time remaining < threshold% of the trading session
# then gets increasingly aggressive, increasing "shave thickness" as time runs out
class Trader_Sniper(Trader):

    def getorder(self, time, countdown, lob, verbose):

        if verbose:
            print("SNPR getorder:")

        lurk_threshold = 0.2
        shavegrowthrate = 3
        shave = int(1.0 / (0.01 + countdown / (shavegrowthrate * lurk_threshold)))
        if (len(self.orders) < 1) or (countdown > lurk_threshold):
            order = None
        else:
            limitprice = self.orders[0].price
            otype = self.orders[0].atype
            ostyle = self.orders[0].astyle
            if otype == 'Bid':
                if lob['bids']['n'] > 0:
                    oprice = lob['bids']['bestp'] + shave
                    if oprice > limitprice:
                        oprice = limitprice
                else:
                    oprice = lob['bids']['worstp']
            else:
                if lob['asks']['n'] > 0:
                    oprice = lob['asks']['bestp'] - shave
                    if oprice < limitprice:
                        oprice = limitprice
                else:
                    oprice = lob['asks']['worstp']
            order = Order(self.tid, otype, ostyle, oprice, self.orders[0].qty, time, None, -1)
            self.lastquote = order
        return order


# Trader subclass ZIP
# As close as we can get it to Cliff 1997
class Trader_ZIP(Trader):

    # ZIP init key param-values are those used in Cliff's 1997 original HP Labs tech report
    # NB this implementation keeps separate margin values for buying & selling,
    #    so a single trader can both buy AND sell
    #    -- in the original, traders were either buyers OR sellers

    def __init__(self, ttype, tid, balance, time):

        Trader.__init__(self, ttype, tid, balance, time)
        m_fix = 0.05
        m_var = 0.3
        self.job = None  # this is 'Bid' or 'Ask' depending on customer order
        self.active = False  # gets switched to True while actively working an order
        self.prev_change = 0  # this was called last_d in Cliff'97
        self.beta = 0.1 + 0.2 * random.random()  # learning rate
        self.momntm = 0.3 * random.random()  # momentum
        self.ca = 0.10  # self.ca & .cr were hard-coded in '97 but parameterised later
        self.cr = 0.10
        self.margin = None  # this was called profit in Cliff'97
        self.margin_buy = -1.0 * (m_fix + m_var * random.random())
        self.margin_sell = m_fix + m_var * random.random()
        self.price = None
        self.limit = None
        # memory of best price & quantity of best bid and ask, on LOB on previous update
        self.prev_best_bid_p = None
        self.prev_best_bid_q = None
        self.prev_best_ask_p = None
        self.prev_best_ask_q = None

    def getorder(self, time, countdown, lob, verbose):
        if len(self.orders) < 1:
            self.active = False
            order = None
        else:
            self.active = True
            self.limit = self.orders[0].price
            self.job = self.orders[0].atype
            if self.job == 'Bid':
                # currently a buyer (working a bid order)
                self.margin = self.margin_buy
            else:
                # currently a seller (working a sell order)
                self.margin = self.margin_sell
            quoteprice = int(self.limit * (1 + self.margin))
            self.price = quoteprice

            order = Order(self.tid, self.job, "LIM", quoteprice, self.orders[0].qty, time, None, -1)
            self.lastquote = order
        return order

    # update margin on basis of what happened in market
    def respond(self, time, lob, trade, verbose):
        # ZIP trader responds to market events, altering its margin
        # does this whether it currently has an order to work or not

        def target_up(price):
            # generate a higher target price by randomly perturbing given price
            ptrb_abs = self.ca * random.random()  # absolute shift
            ptrb_rel = price * (1.0 + (self.cr * random.random()))  # relative shift
            target = int(round(ptrb_rel + ptrb_abs, 0))
            # #                        print('TargetUp: %d %d\n' % (price,target))
            return (target)

        def target_down(price):
            # generate a lower target price by randomly perturbing given price
            ptrb_abs = self.ca * random.random()  # absolute shift
            ptrb_rel = price * (1.0 - (self.cr * random.random()))  # relative shift
            target = int(round(ptrb_rel - ptrb_abs, 0))
            # #                        print('TargetDn: %d %d\n' % (price,target))
            return (target)

        def willing_to_trade(price):
            # am I willing to trade at this price?
            willing = False
            if self.job == 'Bid' and self.active and self.price >= price:
                willing = True
            if self.job == 'Ask' and self.active and self.price <= price:
                willing = True
            return willing

        def profit_alter(price):
            oldprice = self.price
            diff = price - oldprice
            change = ((1.0 - self.momntm) * (self.beta * diff)) + (self.momntm * self.prev_change)
            self.prev_change = change
            newmargin = ((self.price + change) / self.limit) - 1.0

            if self.job == 'Bid':
                if newmargin < 0.0:
                    self.margin_buy = newmargin
                    self.margin = newmargin
            else:
                if newmargin > 0.0:
                    self.margin_sell = newmargin
                    self.margin = newmargin

            # set the price from limit and profit-margin
            self.price = int(round(self.limit * (1.0 + self.margin), 0))

        # #                        print('old=%d diff=%d change=%d price = %d\n' % (oldprice, diff, change, self.price))

        # what, if anything, has happened on the bid LOB?
        bid_improved = False
        bid_hit = False


        lob_best_bid_p = lob['bids']['bestp']
        lob_best_bid_q = None
        if lob_best_bid_p is not None:
            # non-empty bid LOB
            lob_best_bid_q = lob['bids']['lob'][-1][1]
            if self.prev_best_bid_p is None:
                self.prev_best_bid_p = lob_best_bid_p
            elif self.prev_best_bid_p < lob_best_bid_p:
                # best bid has improved
                # NB doesn't check if the improvement was by self
                bid_improved = True
            elif trade is not None and ((self.prev_best_bid_p > lob_best_bid_p) or (
                    (self.prev_best_bid_p == lob_best_bid_p) and (self.prev_best_bid_q > lob_best_bid_q))):
                # previous best bid was hit
                bid_hit = True
        elif self.prev_best_bid_p is not None:
            # the bid LOB has been emptied: was it cancelled or hit?
            last_tape_item = lob['tape'][-1]
            if last_tape_item['type'] == 'Cancel':
                bid_hit = False
            else:
                bid_hit = True

        # what, if anything, has happened on the ask LOB?
        ask_improved = False
        ask_lifted = False
        lob_best_ask_p = lob['asks']['bestp']
        lob_best_ask_q = None
        if lob_best_ask_p is not None:
            # non-empty ask LOB
            lob_best_ask_q = lob['asks']['lob'][0][1]
            if self.prev_best_ask_p is None:
                self.prev_best_ask_p = lob_best_ask_p
            elif self.prev_best_ask_p > lob_best_ask_p:
                # best ask has improved -- NB doesn't check if the improvement was by self
                ask_improved = True
            elif trade is not None and ((self.prev_best_ask_p < lob_best_ask_p) or (
                    (self.prev_best_ask_p == lob_best_ask_p) and (self.prev_best_ask_q > lob_best_ask_q))):
                # trade happened and best ask price has got worse, or stayed same but quantity reduced -- assume previous best ask was lifted
                ask_lifted = True
        elif self.prev_best_ask_p is not None:
            # the ask LOB is empty now but was not previously: canceled or lifted?
            last_tape_item = lob['tape'][-1]
            if last_tape_item['type'] == 'Cancel':
                ask_lifted = False
            else:
                ask_lifted = True

        if verbose and (bid_improved or bid_hit or ask_improved or ask_lifted):
            print ('B_improved', bid_improved, 'B_hit', bid_hit, 'A_improved', ask_improved, 'A_lifted', ask_lifted)

        deal = bid_hit or ask_lifted

        if self.job == 'Ask':
            # seller
            if deal:
                tradeprice = trade['price']
                if self.price <= tradeprice:
                    # could sell for more? raise margin
                    target_price = target_up(tradeprice)
                    profit_alter(target_price)
                elif ask_lifted and self.active and not willing_to_trade(tradeprice):
                    # wouldnt have got this deal, still working order, so reduce margin
                    target_price = target_down(tradeprice)
                    profit_alter(target_price)
            else:
                # no deal: aim for a target price higher than best bid
                if ask_improved and self.price > lob_best_ask_p:
                    if lob_best_bid_p is not None:
                        target_price = target_up(lob_best_bid_p)
                    else:
                        target_price = lob['asks']['worstp']  # stub quote
                    profit_alter(target_price)

        if self.job == 'Bid':
            # buyer
            if deal:
                tradeprice = trade['price']
                if self.price >= tradeprice:
                    # could buy for less? raise margin (i.e. cut the price)
                    target_price = target_down(tradeprice)
                    profit_alter(target_price)
                elif bid_hit and self.active and not willing_to_trade(tradeprice):
                    # wouldnt have got this deal, still working order, so reduce margin
                    target_price = target_up(tradeprice)
                    profit_alter(target_price)
            else:
                # no deal: aim for target price lower than best ask
                if bid_improved and self.price < lob_best_bid_p:
                    if lob_best_ask_p is not None:
                        target_price = target_down(lob_best_ask_p)
                    else:
                        target_price = lob['bids']['worstp']  # stub quote
                    profit_alter(target_price)

        # remember the best LOB data ready for next response
        self.prev_best_bid_p = lob_best_bid_p
        self.prev_best_bid_q = lob_best_bid_q
        self.prev_best_ask_p = lob_best_ask_p
        self.prev_best_ask_q = lob_best_ask_q





# #########################---trader-types have all been defined now--################


def trader_create(lei, robottype, name):
    if robottype == 'GVWY':
        t = Trader_Giveaway('GVWY', name, 0.00, 0)
    elif robottype == 'ZIC':
        t = Trader_ZIC('ZIC', name, 0.00, 0)
    elif robottype == 'SHVR':
        t = Trader_Shaver('SHVR', name, 0.00, 0)
    elif robottype == 'ISHV':
        t = Trader_ISHV('ISHV', name, 0.00, 0)
    elif robottype == 'SNPR':
        t = Trader_Sniper('SNPR', name, 0.00, 0)
    elif robottype == 'ZIP':
        t = Trader_ZIP('ZIP', name, 0.00, 0)
#    elif robottype == 'MAA':
#        t = Trader_AA('MAA', name, 0.00, 0)
    else:
        sys.exit('FATAL: trader_create() doesn\'t know robot type: %s\n' % robottype)

    t.lei = lei
    return t

