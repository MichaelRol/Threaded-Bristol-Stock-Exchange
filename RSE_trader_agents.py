import sys
import math
import random
import threading
from RSE_sys_consts import rse_sys_maxprice
from RSE_msg_classes import Order
# Trader superclass
# all Traders have a trader id, bank balance, blotter, and list of orders to execute
class Trader:

    def __init__(self, ttype, tid, balance, time):
        self.ttype = ttype      # what type / strategy this trader is
        self.tid = tid          # trader unique ID code
        self.balance = balance  # money in the bank
        self.blotter = []       # record of trades executed
        self.orders = {}        # customer orders currently being worked (fixed at 1)
        self.n_quotes = 0       # number of quotes live on LOB
        self.willing = 1        # used in ZIP etc
        self.able = 1           # used in ZIP etc
        self.birthtime = time   # used when calculating age of a trader/strategy
        self.profitpertime = 0  # profit per unit time
        self.n_trades = 0       # how many trades has this trader done?
        self.lastquote = None   # record of what its last quote was


    def __str__(self):
        return '[TID %s type %s balance %s blotter %s orders %s n_trades %s profitpertime %s]' \
                % (self.tid, self.ttype, self.balance, self.blotter, self.orders, self.n_trades, self.profitpertime)


    def add_order(self, order, verbose):
        # in this version, trader has at most one order,
        # if allow more than one, this needs to be self.orders.append(order)
        if self.n_quotes > 0 :
            # this trader has a live quote on the LOB, from a previous customer order
            # need response to signal cancellation/withdrawal of that quote
            response = 'LOB_Cancel'
        else:
            response = 'Proceed'
        self.orders[order.coid] = order
        
        # if len(self.orders) > 3:
        #     self.orders.pop(min(self.orders.keys()))
        if verbose : print('add_order < response=%s' % response)
        return response


    def del_order(self, coid):
        # this is lazy: assumes each trader has only one customer order with quantity=1, so deleting sole order
        # CHANGE TO DELETE THE HEAD OF THE LIST AND KEEP THE TAIL
        self.orders.pop(coid)


    def bookkeep(self, trade, order, verbose, time):

        outstr=""
        # for order in self.orders: outstr = outstr + str(order)

        coid = None
        order_price = None

        if trade['coid'] in self.orders:
            coid = trade['coid']
            order_price = self.orders[coid].price
        elif trade['counter'] in self.orders:
            coid = trade['counter']
            order_price = self.orders[coid].price
        else:
            print("COID not found")
            sys.exit("This is non ideal ngl.")

        self.blotter.append(trade)  # add trade record to trader's blotter
        # NB What follows is **LAZY** -- assumes all orders are quantity=1
        transactionprice = trade['price']
        if self.orders[coid].otype == 'Bid':
            profit = order_price - transactionprice
        else:
            profit = transactionprice - order_price
        self.balance += profit
        self.n_trades += 1
        self.profitpertime = self.balance/(time - self.birthtime)

        # if self.ttype == "GVWY":
        #     print("Order price: " + str(order_price) + ", Trade Price: " + str(transactionprice) + ", Profit: " + str(profit))


        if profit < 0 :
            # print(profit)
            # print(trade)
            # print(order)
            print(str(trade['coid']) + " " + str(trade['counter']) + " " + str(order.coid) + " " + str(self.orders[0].coid))
            sys.exit()

        if verbose: print('%s profit=%d balance=%d profit/time=%d' % (outstr, profit, self.balance, self.profitpertime))
        self.del_order(coid)  # delete the order


    # specify how trader responds to events in the market
    # this is a null action, expect it to be overloaded by specific algos
    def respond(self, time, lob, trade, verbose):
            return None

    # specify how trader mutates its parameter values
    # this is a null action, expect it to be overloaded by specific algos
    def mutate(self, time, lob, trade, verbose):
            return None



# Trader subclass Giveaway
# even dumber than a ZI-U: just give the deal away
# (but never makes a loss)
class Trader_Giveaway(Trader):

    def getorder(self, time, countdown, lob):
        if len(self.orders) < 1:
            order = None
        else:
            coid = max(self.orders.keys())
            quoteprice = self.orders[coid].price
            order = Order(self.tid,
                    self.orders[coid].otype,
                    quoteprice,
                    self.orders[coid].qty,
                    time, self.orders[coid].coid, self.orders[coid].toid)
            self.lastquote=order
            return order



# Trader subclass ZI-C
# After Gode & Sunder 1993
class Trader_ZIC(Trader):

    def getorder(self, time, countdown, lob):

        if len(self.orders) < 1:
            # no orders: return NULL
            order = None
        else:
            coid = max(self.orders.keys())
            minprice = lob['bids']['worst']
            maxprice = lob['asks']['worst']
            limit = self.orders[coid].price
            otype = self.orders[coid].otype
            if otype == 'Bid':
                quoteprice = random.randint(minprice, limit)
            else:
                quoteprice = random.randint(limit, maxprice)
                # NB should check it == 'Ask' and barf if not
            order = Order(self.tid, otype, quoteprice, self.orders[coid].qty, time, self.orders[coid].coid, self.orders[coid].toid)
            self.lastquote = order
        return order


# Trader subclass Shaver
# shaves a penny off the best price
# if there is no best price, creates "stub quote" at system max/min
class Trader_Shaver(Trader):

    def getorder(self, time, countdown, lob):
        if len(self.orders) < 1:
            order = None
        else:
            coid = max(self.orders.keys())
            limitprice = self.orders[coid].price
            otype = self.orders[coid].otype
            if otype == 'Bid':
                if lob['bids']['n'] > 0:
                    quoteprice = lob['bids']['best'] + 1
                    if quoteprice > limitprice :
                        quoteprice = limitprice
                else:
                    quoteprice = lob['bids']['worst']
            else:
                if lob['asks']['n'] > 0:
                    quoteprice = lob['asks']['best'] - 1
                    if quoteprice < limitprice:
                        quoteprice = limitprice
                else:
                    quoteprice = lob['asks']['worst']
            order = Order(self.tid, otype, quoteprice, self.orders[coid].qty, time, self.orders[coid].coid, self.orders[coid].toid)
            self.lastquote = order
        return order


# Trader subclass Sniper
# Based on Shaver,
# "lurks" until time remaining < threshold% of the trading session
# then gets increasing aggressive, increasing "shave thickness" as time runs out
class Trader_Sniper(Trader):

    def getorder(self, time, countdown, lob):
        lurk_threshold = 0.2
        shavegrowthrate = 3
        shave = int(1.0 / (0.01 + countdown / (shavegrowthrate * lurk_threshold)))
        if (len(self.orders) < 1) or (countdown > lurk_threshold):
                order = None
        else:
            coid = max(self.orders.keys())
            limitprice = self.orders[coid].price
            otype = self.orders[coid].otype

            if otype == 'Bid':
                if lob['bids']['n'] > 0:
                    quoteprice = lob['bids']['best'] + shave
                    if quoteprice > limitprice :
                        quoteprice = limitprice
                else:
                    quoteprice = lob['bids']['worst']
            else:
                if lob['asks']['n'] > 0:
                    quoteprice = lob['asks']['best'] - shave
                    if quoteprice < limitprice:
                        quoteprice = limitprice
                else:
                    quoteprice = lob['asks']['worst']
            order = Order(self.tid, otype, quoteprice, self.orders[coid].qty, time, self.orders[coid].coid, self.orders[coid].toid)
            self.lastquote = order
        return order




# Trader subclass ZIP
# After Cliff 1997
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

    def getorder(self, time, countdown, lob):
        if len(self.orders) < 1:
            self.active = False
            order = None
        else:
            coid = max(self.orders.keys())
            self.active = True
            self.limit = self.orders[coid].price
            self.job = self.orders[coid].otype
            if self.job == 'Bid':
                # currently a buyer (working a bid order)
                self.margin = self.margin_buy
            else:
                # currently a seller (working a sell order)
                self.margin = self.margin_sell
            quoteprice = int(self.limit * (1 + self.margin))
            self.price = quoteprice

            order = Order(self.tid, self.job, quoteprice, self.orders[coid].qty, time, self.orders[coid].coid, self.orders[coid].toid)
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


        lob_best_bid_p = lob['bids']['best']
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
        lob_best_ask_p = lob['asks']['best']
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
                        target_price = lob['asks']['worst']  # stub quote
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
                        target_price = lob['bids']['worst']  # stub quote
                    profit_alter(target_price)

        # remember the best LOB data ready for next response
        self.prev_best_bid_p = lob_best_bid_p
        self.prev_best_bid_q = lob_best_bid_q
        self.prev_best_ask_p = lob_best_ask_p
        self.prev_best_ask_q = lob_best_ask_q

# Trader subclass AA
class Trader_AA(Trader):

    def __init__(self, ttype, tid, balance, time):
        # Stuff about trader
        self.ttype = ttype
        self.tid = tid
        self.balance = balance
        self.birthtime = time
        self.profitpertime = 0
        self.n_trades = 0
        self.blotter = []
        self.orders = {}
        self.n_quotes = 0
        self.lastquote = None

        self.limit = None
        self.job = None

        # learning variables
        self.r_shout_change_relative = 0.05
        self.r_shout_change_absolute = 0.05
        self.short_term_learning_rate = random.uniform(0.1, 0.5)
        self.long_term_learning_rate = random.uniform(0.1, 0.5)
        self.moving_average_weight_decay = 0.95 # how fast weight decays with time, lower is quicker, 0.9 in vytelingum
        self.moving_average_window_size = 5
        self.offer_change_rate = 3.0
        self.theta = -2.0
        self.theta_max = 2.0
        self.theta_min = -8.0
        self.marketMax = rse_sys_maxprice

        # Variables to describe the market
        self.previous_transactions = []
        self.moving_average_weights = []
        for i in range(self.moving_average_window_size):
                self.moving_average_weights.append(self.moving_average_weight_decay**i)
        self.estimated_equilibrium = []
        self.smiths_alpha = []
        self.prev_best_bid_p = None
        self.prev_best_bid_q = None
        self.prev_best_ask_p = None
        self.prev_best_ask_q = None

        # Trading Variables
        self.r_shout = None
        self.buy_target = None
        self.sell_target = None
        self.buy_r = -1.0 * (0.3 * random.random())
        self.sell_r = -1.0 * (0.3 * random.random())



    def calcEq(self):
        # Slightly modified from paper, it is unclear inpaper
        # N previous transactions * weights / N in vytelingum, swap N denominator for sum of weights to be correct?
        if len(self.previous_transactions) == 0:
            return
        elif len(self.previous_transactions) < self.moving_average_window_size:
            # Not enough transactions
            self.estimated_equilibrium.append(float(sum(self.previous_transactions)) / max(len(self.previous_transactions), 1))
        else:
            N_previous_transactions = self.previous_transactions[-self.moving_average_window_size:]
            thing = [N_previous_transactions[i]*self.moving_average_weights[i] for i in range(self.moving_average_window_size)]
            eq = sum( thing ) / sum(self.moving_average_weights)
            self.estimated_equilibrium.append(eq)

    def calcAlpha(self):
        alpha = 0.0
        for p in self.estimated_equilibrium:
            alpha += (p - self.estimated_equilibrium[-1])**2
        alpha = math.sqrt(alpha/len(self.estimated_equilibrium))
        self.smiths_alpha.append( alpha/self.estimated_equilibrium[-1] )

    def calcTheta(self):
        gamma = 2.0 #not sensitive apparently so choose to be whatever
        # necessary for intialisation, div by 0
        if min(self.smiths_alpha) == max(self.smiths_alpha):
                alpha_range = 0.4 #starting value i guess
        else:
                alpha_range = (self.smiths_alpha[-1] - min(self.smiths_alpha)) / (max(self.smiths_alpha) - min(self.smiths_alpha))
        theta_range = self.theta_max - self.theta_min
        desired_theta = self.theta_min + (theta_range) * (1 - (alpha_range * math.exp(gamma * (alpha_range - 1))))
        self.theta = self.theta + self.long_term_learning_rate * (desired_theta - self.theta)

    def calcRshout(self):
        p = self.estimated_equilibrium[-1]
        l = self.limit
        theta = self.theta
        if self.job == 'Bid':
            # Currently a buyer
            if l <= p: #extramarginal!
                self.r_shout = 0.0
            else: #intramarginal :(
                if self.buy_target > self.estimated_equilibrium[-1]:
                    #r[0,1]
                    self.r_shout = math.log(((self.buy_target - p) * (math.exp(theta) - 1) / (l - p)) + 1) / theta
                else:
                    #r[-1,0]
                    self.r_shout = math.log((1 - (self.buy_target/p)) * (math.exp(theta) - 1) + 1) / theta


        if self.job == 'Ask':
            # Currently a seller
            if l >= p: #extramarginal!
                self.r_shout = 0
            else: #intramarginal :(
                if self.sell_target > self.estimated_equilibrium[-1]:
                    # r[-1,0]
                    self.r_shout = math.log((self.sell_target - p) * (math.exp(theta) - 1) / (self.marketMax - p) + 1) / theta
                else:
                    # r[0,1]
                    a = (self.sell_target-l)/(p-l)
                    self.r_shout = (math.log((1 - a) * (math.exp(theta) - 1) + 1)) / theta

    def calcAgg(self):
        delta = 0
        if self.job == 'Bid':
            # BUYER
            if self.buy_target >= self.previous_transactions[-1] :
                # must be more aggressive
                delta = (1+self.r_shout_change_relative)*self.r_shout + self.r_shout_change_absolute
            else :
                delta = (1-self.r_shout_change_relative)*self.r_shout - self.r_shout_change_absolute

            self.buy_r = self.buy_r + self.short_term_learning_rate * (delta - self.buy_r)

        if self.job == 'Ask':
            # SELLER
            if self.sell_target > self.previous_transactions[-1] :
                delta = (1+self.r_shout_change_relative)*self.r_shout + self.r_shout_change_absolute
            else :
                delta = (1-self.r_shout_change_relative)*self.r_shout - self.r_shout_change_absolute

            self.sell_r = self.sell_r + self.short_term_learning_rate * (delta - self.sell_r)

    def calcTarget(self):
        if len(self.estimated_equilibrium) > 0:
            p = self.estimated_equilibrium[-1]
            if self.limit == p:
                p = p * 1.000001 # to prevent theta_bar = 0
        elif self.job == 'Bid':
            p = self.limit - self.limit * 0.2  ## Initial guess for eq if no deals yet!!....
        elif self.job == 'Ask':
            p = self.limit + self.limit * 0.2
        l = self.limit
        theta = self.theta
        if self.job == 'Bid':
            #BUYER
            minus_thing = (math.exp(-self.buy_r * theta) - 1) / (math.exp(theta) - 1)
            plus_thing = (math.exp(self.buy_r * theta) - 1) / (math.exp(theta) - 1)
            theta_bar = (theta * l - theta * p) / p
            if theta_bar == 0:
                theta_bar = 0.0001
            if math.exp(theta_bar) - 1 == 0:
                theta_bar = 0.0001
            bar_thing = (math.exp(-self.buy_r * theta_bar) - 1) / (math.exp(theta_bar) - 1)
            if l <= p: #Extramarginal
                if self.buy_r >= 0:
                    self.buy_target = l
                else:
                    self.buy_target = l * (1 - minus_thing)
            else: #intramarginal
                if self.buy_r >= 0:
                    self.buy_target = p + (l-p)*plus_thing
                else:
                    self.buy_target = p*(1-bar_thing)
            if self.buy_target > l:
                self.buy_target = l

        if self.job == 'Ask':
            #SELLER
            minus_thing = (math.exp(-self.sell_r * theta) - 1) / (math.exp(theta) - 1)
            plus_thing = (math.exp(self.sell_r * theta) - 1) / (math.exp(theta) - 1)
            theta_bar = (theta * l - theta * p) / p
            if theta_bar == 0:
                theta_bar = 0.0001
            if math.exp(theta_bar) - 1 == 0:
                theta_bar = 0.0001
            bar_thing = (math.exp(-self.sell_r * theta_bar) - 1) / (math.exp(theta_bar) - 1) #div 0 sometimes what!?
            if l <= p: #Extramarginal
                if self.buy_r >= 0:
                    self.buy_target = l
                else:
                    self.buy_target = l + (self.marketMax - l)*(minus_thing)
            else: #intramarginal
                if self.buy_r >= 0:
                    self.buy_target = l + (p-l)*(1-plus_thing)
                else:
                    self.buy_target = p + (self.marketMax - p)*(bar_thing)
            if self.sell_target is None:
                self.sell_target = l
            elif self.sell_target < l:
                self.sell_target = l

    def getorder(self, time, countdown, lob):
        if len(self.orders) < 1:
            self.active = False
            return None
        else:
            coid = max(self.orders.keys())
            self.active = True
            self.limit = self.orders[coid].price
            self.job = self.orders[coid].otype
            self.calcTarget()

            if self.prev_best_bid_p == None:
                o_bid = 0
            else:
                o_bid = self.prev_best_bid_p
            if self.prev_best_ask_p == None:
                o_ask = self.marketMax
            else:
                o_ask = self.prev_best_ask_p

            if self.job == 'Bid': #BUYER
                if self.limit <= o_bid:
                    return None
                else:
                    if len(self.previous_transactions) > 0: ## has been at least one transaction
                        o_ask_plus = (1+self.r_shout_change_relative)*o_ask + self.r_shout_change_absolute
                        quoteprice = o_bid + ((min(self.limit, o_ask_plus) - o_bid) / self.offer_change_rate)
                    else:
                        if o_ask <= self.buy_target:
                            quoteprice = o_ask
                        else:
                            quoteprice = o_bid + ((self.buy_target - o_bid) / self.offer_change_rate)
            if self.job == 'Ask':
                if self.limit >= o_ask:
                    return None
                else:
                    if len(self.previous_transactions) > 0: ## has been at least one transaction
                        o_bid_minus = (1-self.r_shout_change_relative) * o_bid - self.r_shout_change_absolute
                        quoteprice = o_ask - ((o_ask - max(self.limit, o_bid_minus)) / self.offer_change_rate)
                    else:
                        if o_bid >= self.sell_target:
                                quoteprice = o_bid
                        else:
                                quoteprice = o_ask - ((o_ask - self.sell_target) / self.offer_change_rate)


            order = Order(self.tid, self.job, int(quoteprice), self.orders[coid].qty, time, self.orders[coid].coid, self.orders[coid].toid)
            self.lastquote=order
        return order

    def respond(self, time, lob, trade, verbose):
        ## Begin nicked from ZIP

        # what, if anything, has happened on the bid LOB? Nicked from ZIP..
        bid_hit = False

        lob_best_bid_p = lob['bids']['best']
        lob_best_bid_q = None
        if lob_best_bid_p is not None:
            # non-empty bid LOB
            lob_best_bid_q = lob['bids']['lob'][-1][1]
            if self.prev_best_bid_p is None:
                self.prev_best_bid_p = lob_best_bid_p
            # elif self.prev_best_bid_p < lob_best_bid_p :
            #     # best bid has improved
            #     # NB doesn't check if the improvement was by self
            #     bid_improved = True
            elif trade is not None and ((self.prev_best_bid_p > lob_best_bid_p) or ((self.prev_best_bid_p == lob_best_bid_p) and (self.prev_best_bid_q > lob_best_bid_q))):
                # previous best bid was hit
                bid_hit = True
        elif self.prev_best_bid_p is not None:
            # the bid LOB has been emptied: was it cancelled or hit?
            last_tape_item = lob['tape'][-1]
            if last_tape_item['type'] == 'Cancel' :
                bid_hit = False
            else:
                bid_hit = True

        # what, if anything, has happened on the ask LOB?
        # ask_improved = False
        ask_lifted = False

        lob_best_ask_p = lob['asks']['best']
        lob_best_ask_q = None
        if lob_best_ask_p is not None:
            # non-empty ask LOB
            lob_best_ask_q = lob['asks']['lob'][0][1]
            if self.prev_best_ask_p is None:
                self.prev_best_ask_p = lob_best_ask_p
            # elif self.prev_best_ask_p > lob_best_ask_p :
            #     # best ask has improved -- NB doesn't check if the improvement was by self
            #     ask_improved = True
            elif trade is not None and ((self.prev_best_ask_p < lob_best_ask_p) or ((self.prev_best_ask_p == lob_best_ask_p) and (self.prev_best_ask_q > lob_best_ask_q))):
                # trade happened and best ask price has got worse, or stayed same but quantity reduced -- assume previous best ask was lifted
                ask_lifted = True
        elif self.prev_best_ask_p is not None:
            # the ask LOB is empty now but was not previously: canceled or lifted?
            last_tape_item = lob['tape'][-1]
            if last_tape_item['type'] == 'Cancel' :
                ask_lifted = False
            else:
                ask_lifted = True

        self.prev_best_bid_p = lob_best_bid_p
        self.prev_best_bid_q = lob_best_bid_q
        self.prev_best_ask_p = lob_best_ask_p
        self.prev_best_ask_q = lob_best_ask_q

        deal = bid_hit or ask_lifted

        ## End nicked from ZIP

        if deal:
            self.previous_transactions.append(trade['price'])
            if self.sell_target == None:
                    self.sell_target = trade['price']
            if self.buy_target == None:
                    self.buy_target = trade['price']
            self.calcEq()
            self.calcAlpha()
            self.calcTheta()
            self.calcRshout()
            self.calcAgg()
            self.calcTarget()
            #print 'sell: ', self.sell_target, 'buy: ', self.buy_target, 'limit:', self.limit, 'eq: ',  self.estimated_equilibrium[-1], 'sell_r: ', self.sell_r, 'buy_r: ', self.buy_r, '\n'

class Trader_GDX(Trader):

    def __init__(self, ttype, tid, balance, time):
        self.ttype = ttype
        self.tid = tid
        self.balance = balance
        self.birthtime = time
        self.profitpertime = 0
        self.n_trades = 0
        self.blotter = []
        self.orders = {}
        self.prev_orders = []
        self.n_quotes = 0
        self.lastquote = None
        self.job = None  # this gets switched to 'Bid' or 'Ask' depending on order-type
        self.active = False  # gets switched to True while actively working an order

        #memory of all bids and asks and accepted bids and asks
        self.outstanding_bids = []
        self.outstanding_asks = []
        self.accepted_asks = []
        self.accepted_bids = []

        self.price = -1

        # memory of best price & quantity of best bid and ask, on LOB on previous update
        self.prev_best_bid_p = None
        self.prev_best_bid_q = None
        self.prev_best_ask_p = None
        self.prev_best_ask_q = None

        self.first_turn = True

        self.gamma = 0.1

        self.holdings = 10
        self.remaining_offer_ops = 10
        self.values = [[0 for n in range(self.remaining_offer_ops)] for m in range(self.holdings)]


    def getorder(self, time, countdown, lob):
        if len(self.orders) < 1:
            self.active = False
            order = None
        else:
            coid = max(self.orders.keys())
            self.active = True
            self.limit = self.orders[coid].price
            self.job = self.orders[coid].otype

            #calculate price
            if self.job == 'Bid':
                    self.price = self.calc_p_bid(self.holdings - 1, self.remaining_offer_ops - 1)
            if self.job == 'Ask':
                    self.price = self.calc_p_ask(self.holdings - 1, self.remaining_offer_ops - 1)

            order = Order(self.tid, self.job, int(self.price), self.orders[coid].qty, time, self.orders[coid].coid, self.orders[coid].toid)
            self.lastquote = order

        if self.first_turn or self.price == -1:
            return None
        # if order is not None:
        #     print(order)
        return order

    def calc_p_bid(self, m, n):
        best_return = 0
        best_bid = 0
        # second_best_return = 0
        second_best_bid = 0

        #first step size of 1 get best and 2nd best
        for i in [x*2 for x in range(int(self.limit/2))]:
            thing = self.belief_buy(i) * ((self.limit - i) + self.gamma*self.values[m-1][n-1]) + (1-self.belief_buy(i) * self.gamma * self.values[m][n-1])
            if thing > best_return:
                second_best_bid = best_bid
                # second_best_return = best_return
                best_return = thing
                best_bid = i

        #always best bid largest one
        if second_best_bid > best_bid:
            a = second_best_bid
            second_best_bid = best_bid
            best_bid = a

        #then step size 0.05
        for i in [x*0.05 for x in range(int(second_best_bid), int(best_bid))]:
            thing = self.belief_buy(i + second_best_bid) * ((self.limit - (i + second_best_bid)) + self.gamma*self.values[m-1][n-1]) + (1-self.belief_buy(i + second_best_bid) * self.gamma * self.values[m][n-1])
            if thing > best_return:
                best_return = thing
                best_bid = i + second_best_bid

        return best_bid

    def calc_p_ask(self, m, n):
        best_return = 0
        best_ask = self.limit
        # second_best_return = 0
        second_best_ask = self.limit

        #first step size of 1 get best and 2nd best
        for i in [x*2 for x in range(int(self.limit/2))]:
            j = i + self.limit
            thing =  self.belief_sell(j) * ((j - self.limit) + self.gamma*self.values[m-1][n-1]) + (1-self.belief_sell(j) * self.gamma * self.values[m][n-1])
            if thing > best_return:
                second_best_ask = best_ask
                # second_best_return = best_return
                best_return = thing
                best_ask = j
        #always best ask largest one
        if second_best_ask > best_ask:
            a = second_best_ask
            second_best_ask = best_ask
            best_ask = a

        #then step size 0.05
        for i in [x*0.05 for x in range(int(second_best_ask), int(best_ask))]:
            thing = self.belief_sell(i + second_best_ask) * (((i + second_best_ask) - self.limit) + self.gamma*self.values[m-1][n-1]) + (1-self.belief_sell(i + second_best_ask) * self.gamma * self.values[m][n-1])
            if thing > best_return:
                best_return = thing
                best_ask = i + second_best_ask

        return best_ask

    def belief_sell(self, price):
        accepted_asks_greater = 0
        bids_greater = 0
        unaccepted_asks_lower = 0
        for p in self.accepted_asks:
            if p >= price:
                accepted_asks_greater += 1
        for p in [thing[0] for thing in self.outstanding_bids]:
            if p >= price:
                bids_greater += 1
        for p in [thing[0] for thing in self.outstanding_asks]:
            if p <= price:
                unaccepted_asks_lower += 1

        if accepted_asks_greater + bids_greater + unaccepted_asks_lower == 0:
            return 0
        return (accepted_asks_greater + bids_greater) / (accepted_asks_greater + bids_greater + unaccepted_asks_lower)

    def belief_buy(self, price):
        accepted_bids_lower = 0
        asks_lower = 0
        unaccepted_bids_greater = 0
        for p in self.accepted_bids:
            if p <= price:
                accepted_bids_lower += 1
        for p in [thing[0] for thing in self.outstanding_asks]:
            if p <= price:
                asks_lower += 1
        for p in [thing[0] for thing in self.outstanding_bids]:
            if p >= price:
                unaccepted_bids_greater += 1
        if accepted_bids_lower + asks_lower + unaccepted_bids_greater == 0:
            return 0
        return (accepted_bids_lower + asks_lower) / (accepted_bids_lower + asks_lower + unaccepted_bids_greater)

    def respond(self, time, lob, trade, verbose):
        # what, if anything, has happened on the bid LOB?
        self.outstanding_bids = lob['bids']['lob']
        # bid_improved = False
        # bid_hit = False
        lob_best_bid_p = lob['bids']['best']
        lob_best_bid_q = None
        if lob_best_bid_p is not None:
            # non-empty bid LOB
            lob_best_bid_q = lob['bids']['lob'][-1][1]
            if self.prev_best_bid_p is None:
                self.prev_best_bid_p = lob_best_bid_p
            # elif self.prev_best_bid_p < lob_best_bid_p :
            #     # best bid has improved
            #     # NB doesn't check if the improvement was by self
            #     bid_improved = True

            elif trade is not None and ((self.prev_best_bid_p > lob_best_bid_p) or ((self.prev_best_bid_p == lob_best_bid_p) and (self.prev_best_bid_q > lob_best_bid_q))):
                # previous best bid was hit
                self.accepted_bids.append(self.prev_best_bid_p)
                # bid_hit = True
        # elif self.prev_best_bid_p is not None:
        #     # the bid LOB has been emptied: was it cancelled or hit?
        #     last_tape_item = lob['tape'][-1]
            # if last_tape_item['type'] == 'Cancel' :
            #     bid_hit = False
            # else:
            #     bid_hit = True

        # what, if anything, has happened on the ask LOB?
        self.outstanding_asks = lob['asks']['lob']
        # ask_improved = False
        # ask_lifted = False
        lob_best_ask_p = lob['asks']['best']
        lob_best_ask_q = None
        
        if lob_best_ask_p is not None:
            # non-empty ask LOB
            lob_best_ask_q = lob['asks']['lob'][0][1]
            if self.prev_best_ask_p is None:
                self.prev_best_ask_p = lob_best_ask_p
            # elif self.prev_best_ask_p > lob_best_ask_p :
                # best ask has improved -- NB doesn't check if the improvement was by self
                # ask_improved = True
            elif trade is not None and ((self.prev_best_ask_p < lob_best_ask_p) or ((self.prev_best_ask_p == lob_best_ask_p) and (self.prev_best_ask_q > lob_best_ask_q))):
                # trade happened and best ask price has got worse, or stayed same but quantity reduced -- assume previous best ask was lifted
                self.accepted_asks.append(self.prev_best_ask_p)
                # ask_lifted = True
        # elif self.prev_best_ask_p is not None:
            # the ask LOB is empty now but was not previously: canceled or lifted?
            # last_tape_item = lob['tape'][-1]
            # if last_tape_item['type'] == 'Cancel' :
            #     ask_lifted = False
            # else:
            #     ask_lifted = True


        #populate expected values
        if self.first_turn:
            self.first_turn = False
            for n in range(1, self.remaining_offer_ops):
                for m in range(1, self.holdings):
                    if self.job == 'Bid':
                        #BUYER
                        self.values[m][n] = self.calc_p_bid(m, n)

                    if self.job == 'Ask':
                        #BUYER
                        self.values[m][n] = self.calc_p_ask(m, n)


        # deal = bid_hit or ask_lifted


        # remember the best LOB data ready for next response
        self.prev_best_bid_p = lob_best_bid_p
        self.prev_best_bid_q = lob_best_bid_q
        self.prev_best_ask_p = lob_best_ask_p
        self.prev_best_ask_q = lob_best_ask_q




##########################---trader-types have all been defined now--################