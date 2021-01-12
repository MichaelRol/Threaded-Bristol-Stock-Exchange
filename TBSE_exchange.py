import sys
from TBSE_sys_consts import tbse_sys_minprice, tbse_sys_maxprice


# Minor adaptations from original BSE code by Dave Cliff

# Orderbook_half is one side of the book: a list of bids or a list of asks, each sorted best-first
class Orderbook_half:

    def __init__(self, booktype, worstprice):
        # booktype: bids or asks?
        self.booktype = booktype
        # dictionary of orders received, indexed by Trader ID
        self.orders = {}
        # limit order book, dictionary indexed by price, with order info
        self.lob = {}
        # anonymized LOB, lists, with only price/qty info
        self.lob_anon = []
        # summary stats
        self.best_price = None
        self.best_tid = None
        self.worstprice = worstprice
        self.n_orders = 0  # how many orders?
        self.lob_depth = 0  # how many different prices on lob?


    def anonymize_lob(self):
        # anonymize a lob, strip out order details, format as a sorted list
        # NB for asks, the sorting should be reversed
        self.lob_anon = []
        for price in list(sorted(self.lob)):
            qty = self.lob[price][0]
            self.lob_anon.append([price, qty])


    def build_lob(self):
        lob_verbose = False
        # take a list of orders and build a limit-order-book (lob) from it
        # NB the exchange needs to know arrival times and trader-id associated with each order
        # returns lob as a dictionary (i.e., unsorted)
        # also builds anonymized version (just price/quantity, sorted, as a list) for publishing to traders
        self.lob = {}
        
        for tid in list(self.orders):
        # 	order = orders_cp.get(tid)
            order = self.orders.get(tid)
            price = order.price
            if price in self.lob:
                # update existing entry
                qty = self.lob[price][0]
                orderlist = self.lob[price][1]
                orderlist.append([order.time, order.qty, order.tid, order.toid])
                self.lob[price] = [qty + order.qty, orderlist]
            else:
                # create a new dictionary entry
                self.lob[price] = [order.qty, [[order.time, order.qty, order.tid, order.toid]]]
        # create anonymized version
        self.anonymize_lob()
        # record best price and associated trader-id
        if len(self.lob) > 0 :
            if self.booktype == 'Bid':
                self.best_price = self.lob_anon[-1][0]
            else :
                self.best_price = self.lob_anon[0][0]
            self.best_tid = self.lob[self.best_price][1][0][2]
        else :
            self.best_price = None
            self.best_tid = None

        if lob_verbose : print(self.lob)


    def book_add(self, order):
        # add order to the dictionary holding the list of orders
        # either overwrites old order from this trader
        # or dynamically creates new entry in the dictionary
        # so, max of one order per trader per list
        # checks whether length or order list has changed, to distinguish addition/overwrite
        
        n_orders = self.n_orders
        self.orders[order.tid] = order
        self.n_orders = len(self.orders)
        self.build_lob()
        
        if n_orders != self.n_orders :
            return('Addition')
        else:
            return('Overwrite')



    def book_del(self, order):
        # delete order from the dictionary holding the orders
        # assumes max of one order per trader per list
        # checks that the Trader ID does actually exist in the dict before deletion
        
        if self.orders.get(order.tid) != None :
            del(self.orders[order.tid])
            self.n_orders = len(self.orders)
            self.build_lob()


    def delete_best(self):
        # delete order: when the best bid/ask has been hit, delete it from the book
        # the TraderID of the deleted order is return-value, as counterparty to the trade
        best_price_orders = self.lob[self.best_price]
        best_price_qty = best_price_orders[0]
        best_price_counterparty = best_price_orders[1][0][2]
        if best_price_qty == 1:
            # here the order deletes the best price
            del(self.lob[self.best_price])
            del(self.orders[best_price_counterparty])
            self.n_orders = self.n_orders - 1
            if self.n_orders > 0:
                if self.booktype == 'Bid':
                    self.best_price = max(self.lob.keys())
                else:
                    self.best_price = min(self.lob.keys())
                self.lob_depth = len(self.lob.keys())
            else:
                self.best_price = self.worstprice
                self.lob_depth = 0
        else:
            # best_bid_qty>1 so the order decrements the quantity of the best bid
            # update the lob with the decremented order data
            self.lob[self.best_price] = [best_price_qty - 1, best_price_orders[1][1:]]

            # update the bid list: counterparty's bid has been deleted
            del(self.orders[best_price_counterparty])
            self.n_orders = self.n_orders - 1
        self.build_lob()
        return best_price_counterparty



# Orderbook for a single instrument: list of bids and list of asks

class Orderbook(Orderbook_half):

    def __init__(self):
        self.bids = Orderbook_half('Bid', tbse_sys_minprice)
        self.asks = Orderbook_half('Ask', tbse_sys_maxprice)
        self.tape = []
        self.quote_id = 0  #unique ID code for each quote accepted onto the book



# Exchange's internal orderbook

class Exchange(Orderbook):

    def add_order(self, order, verbose):
        # add a quote/order to the exchange and update all internal records; return unique i.d.
        order.toid = self.quote_id
        self.quote_id = order.toid + 1
        
        if verbose : print('QUID: order.quid=%d self.quote.id=%d' % (order.qid, self.quote_id))
        
        if order.otype == 'Bid':
            response=self.bids.book_add(order)
            best_price = self.bids.lob_anon[-1][0]
            self.bids.best_price = best_price
            self.bids.best_tid = self.bids.lob[best_price][1][0][2]
        else:
            response=self.asks.book_add(order)
            best_price = self.asks.lob_anon[0][0]
            self.asks.best_price = best_price
            self.asks.best_tid = self.asks.lob[best_price][1][0][2]
        return [order.toid, response]


    def del_order(self, time, order, verbose):
        # delete a trader's quot/order from the exchange, update all internal records
        
        if order.otype == 'Bid':
            self.bids.book_del(order)
            if self.bids.n_orders > 0 :
                best_price = self.bids.lob_anon[-1][0]
                self.bids.best_price = best_price
                self.bids.best_tid = self.bids.lob[best_price][1][0][2]
            else: # this side of book is empty
                self.bids.best_price = None
                self.bids.best_tid = None
            cancel_record = { 'type': 'Cancel', 'time': time, 'order': order }
            self.tape.append(cancel_record)

        elif order.otype == 'Ask':
            self.asks.book_del(order)
            if self.asks.n_orders > 0 :
                best_price = self.asks.lob_anon[0][0]
                self.asks.best_price = best_price
                self.asks.best_tid = self.asks.lob[best_price][1][0][2]
            else: # this side of book is empty
                self.asks.best_price = None
                self.asks.best_tid = None
            cancel_record = { 'type': 'Cancel', 'time': time, 'order': order }
            self.tape.append(cancel_record)
        else:
            # neither bid nor ask?
            sys.exit('bad order type in del_quote()')

    # this returns the LOB data "published" by the exchange,
    # i.e., what is accessible to the traders
    def publish_lob(self, time, verbose):
        public_data = {}
        public_data['time'] = time
        public_data['bids'] = {'best':self.bids.best_price,
                                'worst':self.bids.worstprice,
                                'n': self.bids.n_orders,
                                'lob':self.bids.lob_anon}
        public_data['asks'] = {'best':self.asks.best_price,
                                'worst':self.asks.worstprice,
                                'n': self.asks.n_orders,
                                'lob':self.asks.lob_anon}
        public_data['QID'] = self.quote_id
        public_data['tape'] = self.tape
        if verbose:
            print('publish_lob: t=%d' % time)
            print('BID_lob=%s' % public_data['bids']['lob'])
            print('ASK_lob=%s' % public_data['asks']['lob'])

        return public_data



    def process_order2(self, time, order, verbose):
        # receive an order and either add it to the relevant LOB (ie treat as limit order)
        # or if it crosses the best counterparty offer, execute it (treat as a market order)
        oprice = order.price
        counterparty = None
        counter_coid = None
        [toid, response] = self.add_order(order, verbose)  # add it to the order lists -- overwriting any previous order
        order.toid = toid
        if verbose :
            print('TOID: order.toid=%d' % order.toid)
            print('RESPONSE: %s' % response)
        best_ask = self.asks.best_price
        best_ask_tid = self.asks.best_tid
        best_bid = self.bids.best_price
        best_bid_tid = self.bids.best_tid
        if order.otype == 'Bid':
            if self.asks.n_orders > 0 and best_bid >= best_ask:
                # bid lifts the best ask
                if verbose: print("Bid $%s lifts best ask" % oprice)
                counterparty = best_ask_tid
                counter_coid = self.asks.orders[counterparty].coid
                price = best_ask  # bid crossed ask, so use ask price
                if verbose: print('counterparty, price', counterparty, price)
                # delete the ask just crossed
                self.asks.delete_best()
                # delete the bid that was the latest order
                self.bids.delete_best()
        elif order.otype == 'Ask':
            if self.bids.n_orders > 0 and best_ask <= best_bid:
                # ask hits the best bid
                if verbose: print("Ask $%s hits best bid" % oprice)
                # remove the best bid
                counterparty = best_bid_tid
                counter_coid = self.bids.orders[counterparty].coid
                price = best_bid  # ask crossed bid, so use bid price
                if verbose: print('counterparty, price', counterparty, price)
                # delete the bid just crossed, from the exchange's records
                self.bids.delete_best()
                # delete the ask that was the latest order, from the exchange's records
                self.asks.delete_best()
        else:
            # we should never get here
            sys.exit('process_order() given neither Bid nor Ask')
        # NB at this point we have deleted the order from the exchange's records
        # but the two traders concerned still have to be notified
        if verbose: print('counterparty %s' % counterparty)

        lob = self.publish_lob(time, False)
        if counterparty != None:
            # process the trade
            if verbose: print('>>>>>>>>>>>>>>>>>TRADE t=%5.2f $%d %s %s' % (time, price, counterparty, order.tid))
            transaction_record = { 'type': 'Trade',
                                    'time': time,
                                    'price': price,
                                    'party1':counterparty,
                                    'party2':order.tid,
                                    'qty': order.qty,
                                    'coid': order.coid,
                                    'counter': counter_coid 
                                    }
            self.tape.append(transaction_record)
            return (transaction_record, lob)
        else:
            return (None, lob)



    def tape_dump(self, fname, fmode, tmode):
        dumpfile = open(fname, fmode)
        for tapeitem in self.tape:
            if tapeitem['type'] == 'Trade' :
                dumpfile.write('%s, %s\n' % (tapeitem['time'], tapeitem['price']))
        dumpfile.close()
        if tmode == 'wipe':
            self.tape = []



