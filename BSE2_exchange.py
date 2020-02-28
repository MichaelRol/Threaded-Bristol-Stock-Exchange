# -*- coding: utf-8 -*-
#
# BSE: The Bristol Stock Exchange
#
# Version 2.1Beta: Nov 20th, 2018.
# Version 1.4: August 30th, 2018.
# Version 1.3: July 21st, 2018.
# Version 1.2: November 17th, 2012.
#
# Copyright (c) 2012-2020, Dave Cliff
#
#
# ------------------------
#
# MIT Open-Source License:
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
# LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# ------------------------
#
#
#
# BSE is a very simple simulation of automated execution traders
# operating on a very simple model of a limit order book (LOB) exchange
#
# major simplifications in this version:
#       (a) only one financial instrument being traded
#       (b) each trader can have max of one order per single orderbook.
#       (c) simply processes each order in sequence and republishes LOB to all traders
#           => no issues with exchange processing latency/delays or simultaneously issued orders.
#
# NB this code has been written to be readable/intelligible, not efficient!


import sys

from BSE2_sys_consts import bse_sys_minprice, bse_sys_maxprice

from BSE2_msg_classes import Order, ExchMsg


# Orderbook_half is one side of the book:
# The internal records of the exchange include the ID of the trader who issued the order, arrival time, etc.
# The externally published LOB aggregates and anonymizes these details.

class Orderbook_half:

    def __init__(self, booktype, worstprice):

        self.booktype = booktype

        def bid_equaltoorbetterthan(p1, p2, verbose):
            if verbose:
                print("bid_equaltoorbetterthan: %d >= %d ?" % (p1, p2))
            if p1 >= p2:
                return True
            else:
                return False

        def ask_equaltoorbetterthan(p1, p2, verbose):
            if verbose:
                print("ask_equaltoorbetterthan: %d <= %d ?" % (p1, p2))
            if p1 <= p2:
                return True
            else:
                return False

        # function for deciding whether price A is equal to or better than price B
        if self.booktype == 'Bid':
            self.equaltoorbetterthan = bid_equaltoorbetterthan
        elif self.booktype == 'Ask':
            self.equaltoorbetterthan = ask_equaltoorbetterthan
        else:
            sys.exit('Fail: Orderbook_half __init__ passed booktype=%s', str(booktype))

        # dictionary of live orders received, indexed by Order ID
        self.orders = {}
        # limit order book, exchange's internal list, ordered by price, with associated order info
        self.lob = []
        # anonymized LOB, aggregated list with only price/qty info: as published to market observers
        self.lob_anon = []
        # list of orders "resting" at the exchange, i.e. orders that persist for some time (e.g. AON, ICE)
        self.resting = []
        # On-Close & On-Open hold LIM & MKT orders that execute at market open and close (MOO, MOC, LOO, LOC)
        self.on_close = []
        self.on_open = []
        # OXO stores details of "other" for OSO and OCO orders
        self.oxo = []
        # summary stats
        self.best_price = None
        self.worst_price = worstprice
        self.n_orders = None  # how many orders?
        # self.lob_depth = 0  # how many different prices on lob?

    def __str__(self):
        v = 'OB_H> '
        s = '\n' + v + self.booktype + '\n'
        s = s + v + 'Orders: '
        for oid in self.orders:
            s = s + str(oid) + '=' + str(self.orders[oid]) + ' '
        s = s + '\n'
        s = s + v + 'LOB:\n'
        for row in self.lob:
            s = s + '[P=%d,[' % row[0]  # price
            for order in row[1]:
                s = s + '[T=%5.2f Q=%d %s OID:%d]' % (order[0], order[1], order[2], order[3])
            s = s + ']]\n'
        s = s + v + 'LOB_anon' + str(self.lob_anon) + '\n'
        s = s + v + 'MOB:'
        s = s + '\n'

        return s

    def anonymize_lob(self, verbose):
        # anonymize a lob, strip out order details, format as a sorted list
        # sorting is best prices at the front (LHS) of the list
        self.lob_anon = []
        if self.booktype == 'Bid':
            for price in sorted(self.lob, reverse=True):
                qty = self.lob[price][0]
                self.lob_anon.append([price, qty])
        elif self.booktype == 'Ask':
            for price in sorted(self.lob):
                qty = self.lob[price][0]
                self.lob_anon.append([price, qty])
        else:
            sys.exit('Fail: Orderbook_half __init__ passed booktype=%s' % str(self.booktype))
        if verbose:
            print(self.lob_anon)

    def build_lob(self, verbose):
        # take a list of orders and build a limit-order-book (lob) from it
        # NB the exchange needs to know arrival times and trader-id associated with each order
        # returns lob as a list, sorted by price best to worst, orders at same price sorted by arrival time
        # also builds aggregated & anonymized version (just price/quantity, sorted, as a list) for publishing to traders

        # First builds lob as a dictionary indexed by price
        lob = {}
        for oid in self.orders:
            order = self.orders.get(oid)
            price = int(order.price)
            if price in lob:
                # update existing entry
                qty = lob[price][0]
                orderlist = lob[price][1]
                orderlist.append([order.time, order.qty, order.tid, order.orderid])
                lob[price] = [qty + order.qty, orderlist]
            else:
                # create a new dictionary entry
                lob[price] = [order.qty, [[order.time, order.qty, order.tid, order.orderid]]]

        self.lob = []
        for price in lob:
            orderlist = lob[price][1]
            orderlist.sort()  # orders are sorted by arrival time
            self.lob.append([price, orderlist])  # appends only the price and the order-list
        # now sort by price: order depends on book type
        if self.booktype == 'Bid':
            self.lob.sort(reverse=True)
        elif self.booktype == 'Ask':
            self.lob.sort()
        else:
            sys.exit('Fail: Orderbook_half __init__ passed booktype=%s' % str(self.booktype))

        # create anonymized version of LOB for publication
        self.lob_anon = []
        if self.booktype == 'Bid':
            for price in sorted(lob, reverse=True):
                qty = lob[price][0]
                self.lob_anon.append([price, qty])
        else:
            for price in sorted(lob):
                qty = lob[price][0]
                self.lob_anon.append([price, qty])

        if verbose:
            print(self.lob_anon)

        # record best price and associated trader-id
        if len(self.lob) > 0:
            if self.booktype == 'Bid':
                self.best_price = self.lob_anon[-1][0]  # assumes reverse order COME BACK HERE
            else:
                self.best_price = self.lob_anon[0][0]
        else:
            self.best_price = None

        if verbose:
            print(self.lob)

    def book_add(self, order, verbose):
        # add an order to the master list holding the orders
        if verbose:
            print('>book_add %s' % order)
        self.orders[order.orderid] = order
        self.n_orders = len(self.orders)
        # reconstruct the LOB -- from scratch (inefficient)
        self.build_lob(verbose)
        return None  # null response

    def book_CAN(self, time, order, pool_id, verbose):
        # delete (CANcel) an order from the dictionary holding the orders

        def add_tapeitem(eventlist, can_pool_id, can_time, can_oid, otype, qty, verbosity):
            # add_tapeitem(): add an event to list of events that will be written to tape
            tape_event = {'pool_id': can_pool_id,
                          'type': 'CAN',
                          'time': can_time,
                          'oid': can_oid,
                          'otype': otype,
                          'o_qty': qty}
            eventlist.append(tape_event)
            if verbosity:
                print('book_CAN.add_tapeitem() trans_event=%s' % tape_event)

        tape_events = []

        if verbose:
            print('>OrderbookHalf.book_CAN %s' % order)
            for this_order in self.orders:
                print("{%s: %s}" % (this_order, str(self.orders[this_order])))

        oid = order.orderid
        if len(self.orders) > 0 and (self.orders.get(oid) is not None):
            if verbose:
                print('Deleting order %s' % oid)
            o_qty = self.orders[oid].qty
            o_type = self.booktype
            del (self.orders[oid])
            self.n_orders = len(self.orders)
            # reconstruct the LOB -- from scratch (inefficient)
            self.build_lob(verbose)
            if verbose:
                print('<book_CAN %s' % self.orders)

            tmsg = ExchMsg(order.tid, oid, "CAN", [], None, 0, 0)
            add_tapeitem(tape_events, pool_id, time, oid, o_type, o_qty, verbose)

            return {"TraderMsgs": [tmsg], "TapeEvents": tape_events}
        else:
            print('NOP')  # no operation -- order ID not in the order dictionary
            sys.exit('Fail: book_CAN() attempts to delete nonexistent order ')

    def book_take(self, time, order, pool_id, verbose):
        # process the order by taking orders off the LOB, consuming liquidity at the top of the book
        # this is where (MKT, IOC, FOK, AON) orders get matched and execute
        # returns messages re transactions, to be sent to traders involved; and a list of events to write to the tape
        # MKT order consumes the specified quantity, if available: partial fills allowed; ...
        #       ...ignores the price (so watch out for loss-making trades)
        # FOK only completes if it can consume the specified quantity at prices equal to or better than specified price
        # IOC executes as much as it can of the specified quantity; allows partial fill: ...
        #       ...unfilled portion of order is cancelled
        # AON is like FOK but rests at the exchange until either (a) it can do complete fill or ...
        #       ...(b) clock reaches specified expiry time, at which point order cancelled.
        # NB the cancellations are not written to the tape, because they do not take liquidity away from the LOB

        def add_msg(msglist, tid, oid, etype, transactions, rev_order, exchange_fee, verbosity):
            # add_msg(): add a message to list of messages from exchange back to traders
            # each msg tells trader [tid] that [OID] resulted in an event-type from [PART|FILL|FAIL]
            # if PART then also sends back [revised order] ...
            #      ... telling the trader what the LOB retains as the unfilled portion
            # if FILL then [revised order] is None
            # message concludes with bank-balance details: exchange fee & trader's balance at exchange
            new_msg = ExchMsg(tid, oid, etype, transactions, rev_order, exchange_fee, 0)
            msglist.append(new_msg)
            if verbosity:
                print(new_msg)

        def add_tapeitem(eventlist, pool, eventtype, eventtime, eventprice, event_qty, party_from, party_to, verbosity):
            # add_tapeitem(): add an event to list of events that will be written to tape
            # event type within book_take should be 'Trade'
            tape_event = {'pool_id': pool,
                          'type': eventtype,
                          'time': eventtime,
                          'price': eventprice,
                          'qty': event_qty,
                          'party1': party_from,
                          'party2': party_to}
            eventlist.append(tape_event)
            if verbosity:
                print('add_tapeitem() tape_event=%s' % tape_event)

        msg_list = []  # details of orders consumed from the LOB when filling this order
        trnsctns = []  # details of transactions resulting from this incoming order walking the book
        tape_events = []  # details of transaction events to be written onto tape
        qty_filled = 0  # how much of this order have we filled so far?
        fee = 333  # exchange fee charged for processing this order (taking liquidity, wrt maker-taker)

        if verbose:
            print('>book_take(): order=%s, lob=%s' % (order, self.lob))

        # initial checks, return FAIL if there is simply no hope of executing this order

        if len(self.lob) == 0:
            # no point going any further; LOB is empty
            add_msg(msg_list, order.tid, order.orderid, "FAIL", [], None, fee, verbose)
            return {"TraderMsgs": msg_list, "TapeEvents": tape_events}

        # how deep is the book? (i.e. what is cumulative qty available) at this order's indicated price level?
        depth = 0
        for level in self.lob_anon:
            if self.equaltoorbetterthan(level[0], order.price, verbose):
                depth += level[1]
            else:  # we're past the level in the LOB where the prices are good for this order
                break

        if order.ostyle == "FOK" or order.ostyle == "AON":
            # FOK and AON require a complete fill
            # so we first check that this order can in principle be filled: is there enough liquidity available?
            if depth < order.qty:
                # there is not enough depth at prices that allow this order to completely fill
                add_msg(msg_list, order.tid, order.oid, "FAIL", [], None, fee, verbose)
                # NB here book_take() sends a msg back that an AON order is FAIL, that needs to be picked up by the
                # exchange logic and not passed back to the trader concerned, unless the AON has actually timed out
                return {"TraderMsgs": msg_list, "TapeEvents": tape_events}

        if order.ostyle == "IOC" and depth < 1:
            # IOC order is a FAIL because there is no depth at all for the indicated price
            add_msg(msg_list, order.tid, order.orderid, "FAIL", [], None, fee, verbose)
            return {"TraderMsgs": msg_list, "TapeEvents": tape_events}

        # we only get this far if:
        # LOB is not empty
        # order is FOK or AON (complete fill only) --  we know there's enough depth to complete
        # order is MKT (allows partial fill, ignores prices, stops when indicated quantity is reached or LOB is empty)
        # order is IOC (allows partial fill, aims for indicated quantity but stops when price-limit is reached or LOB...
        # ...is empty) and LOB depth at price > 0

        if order.otype == "Bid":
            tid_to = order.tid
            oid_to = order.orderid
        elif order.otype == "Ask":
            tid_from = order.tid
            oid_from = order.orderid
        else:  # this shouldn't happen
            sys.exit('>book_take: order.otype=%s in book_take' % order.otype)

        # make a copy of the order-list and lobs as it initially stands
        # used for reconciling fills and when order is abandoned because it can't complete (e.g. FOK, AON)
        # initial_orders = self.orders

        # work this order by "walking the book"

        qty_remaining = order.qty

        best_lob_price = self.lob[0][0]

        good_price = True

        if order.ostyle != "MKT":
            good_price = self.equaltoorbetterthan(best_lob_price, order.price, verbose)

        # this while loop consumes the top of the LOB while trying to fill the order
        while good_price and (qty_remaining > 0) and (len(self.orders) > 0):

            good_price = self.equaltoorbetterthan(self.lob[0][0], order.price, verbose)

            if verbose:
                print('BK_TAKE: qty_rem=%d; lob=%s; good_price=%s' % (qty_remaining, str(self.lob), good_price))
                sys.stdout.flush()

            if order.ostyle == "IOC" and (not good_price):
                # current LOB best price is unacceptable for IOC
                if verbose:
                    print('BK_TAKE: IOC breaks out of while loop (otype=%s best LOB price = %d; order price = %d)' %
                          (order.otype, self.lob[0][0], order.price))
                break  # out of the while loop

            best_lob_price = self.lob[0][0]
            best_lob_orders = self.lob[0][1]
            best_lob_order = best_lob_orders[0]
            best_lob_order_qty = best_lob_order[1]
            best_lob_order_tid = best_lob_order[2]
            best_lob_order_oid = best_lob_order[3]

            if order.otype == "Bid":
                tid_from = best_lob_order_tid
                oid_from = best_lob_order_oid
            elif order.otype == "Ask":
                tid_to = best_lob_order_tid
                oid_to = best_lob_order_oid

            if verbose:
                print('BK_TAKE: best_lob _price=%d _order=%s qty=%d oid_from=%d oid_to=%d tid_from=%s tid_to=%s\n' %
                      (best_lob_price, best_lob_order, best_lob_order_qty, oid_from, oid_to, tid_from, tid_to))

            # walk the book: does this order consume current best order on book?
            if best_lob_order_qty >= qty_remaining:

                # incoming liquidity-taking order is completely filled by consuming some/all of best order on LOB
                qty = qty_remaining
                price = best_lob_price
                qty_filled = qty_filled + qty
                best_lob_order_qty = best_lob_order_qty - qty
                # the incoming order is a complete fill
                transaction = {"Price": price, "Qty": qty}
                trnsctns.append(transaction)

                # add a message to the list of outgoing messages from exch to traders
                add_msg(msg_list, order.tid, order.orderid, "FILL", trnsctns, None, fee, verbose)

                # add a record of this to the tape (NB this identifies both parties to the trade, so only do it once)
                add_tapeitem(tape_events, pool_id, 'Trade', time, price, qty, tid_from, tid_to, verbose)

                # so far have dealt with effect of match on incoming order
                # now need to deal with effect of match on best order on LOB (the other side of the deal)
                if best_lob_order_qty > 0:
                    # the best LOB order is only partially consumed
                    best_lob_order[1] = best_lob_order_qty
                    best_lob_orders[0] = best_lob_order
                    self.lob[0][1] = best_lob_orders
                    self.orders[best_lob_order_oid].qty = best_lob_order_qty
                    # The LOB order it matched against is only a partial fill
                    add_msg(msg_list, best_lob_order_tid, best_lob_order_oid, "PART", [transaction],
                            self.orders[best_lob_order_oid], fee, verbose)
                    # add_tapeitem(tape_events, 'Trade', time, price, qty, tid_from, tid_to, verbose)
                else:
                    # the best LOB order is fully consumed: delete it from LOB
                    del (best_lob_orders[0])
                    del (self.orders[best_lob_order_oid])
                    # The LOB order it matched against also complete
                    add_msg(msg_list, best_lob_order_tid, best_lob_order_oid, "FILL", [transaction], None, fee, verbose)
                    # add_tapeitem(tape_events, 'Trade', time, price, qty, tid_from, tid_to, verbose)
                    # check: are there other remaining orders at this price?
                    if len(best_lob_orders) > 0:
                        # yes
                        self.lob[0][1] = best_lob_orders
                    else:
                        # no
                        del (self.lob[0])  # consumed the last order on the LOB at this price
                qty_remaining = 0  # liquidity-taking all done
            else:
                # order is only partially filled by current best order, but current best LOB order is fully filled
                # consume all the current best and repeat
                qty = best_lob_order_qty
                price = best_lob_price
                qty_filled = qty_filled + qty
                transaction = {"Price": price, "Qty": qty}
                trnsctns.append(transaction)

                # add a message to the list of outgoing messages from exch to traders
                add_msg(msg_list, best_lob_order_tid, best_lob_order_oid, "FILL", [transaction], None, fee, verbose)

                # add a record of this to the tape (NB this identifies both parties to the trade, so only do it once)
                add_tapeitem(tape_events, pool_id, 'Trade', time, price, qty, tid_from, tid_to, verbose)

                # the best LOB order is fully consumed: delete it from LOB and from order-list
                del (self.orders[best_lob_order_oid])
                del (best_lob_orders[0])

                # check: are there other remaining orders at this price?
                if len(best_lob_orders) > 0:
                    # yes
                    self.lob[0][1] = best_lob_orders
                else:
                    # no
                    del (self.lob[0])  # consumed the last order on the LOB at this price

                qty_remaining = qty_remaining - qty
                if verbose:
                    print('New LOB=%s orders=%s' % (str(self.lob), str(self.orders)))

        # main while loop ends here

        # when we get to here either...
        # the order completely filled by consuming the front of the book (which may have emptied the whole book)
        # or the whole book was consumed (and is now empty) without completely filling the order
        # or IOC consumed as much of the book's availability at the order's indicated price (good_price = False)

        if qty_remaining > 0:
            if qty_remaining == order.qty:
                # this order is wholly unfilled: that's a FAIL (how did this get past the initial checks?)
                add_msg(msg_list, order.tid, order.orderid, "FAIL", [], None, fee, verbose)
            else:
                # this liquidity-taking order only partially filled but ran out of usable LOB
                order.qty = qty_remaining  # revise the order quantity
                add_msg(msg_list, order.tid, order.orderid, "PART", trnsctns, order, fee, verbose)
                # add_tapeitem(tape_events, 'Trade', time, price, qty, tid_from, tid_to, verbose)

        if verbose:
            print('<Orderbook_Half.book_take() TapeEvents=%s' % tape_events)
            print('<Orderbook_Half.book_take() TraderMsgs=')
            for msg in msg_list:
                print('%s,' % str(msg))
            print('\n')

        # rebuild the lob to reflect the adjusted order list
        self.build_lob(verbose)

        return {"TraderMsgs": msg_list, "TapeEvents": tape_events}


# Orderbook for a single instrument: list of bids and list of asks and methods to manipulate them

class Orderbook(Orderbook_half):

    def __init__(self, id_string):
        self.idstr = id_string  # give it a name
        self.bids = Orderbook_half('Bid', bse_sys_minprice)
        self.asks = Orderbook_half('Ask', bse_sys_maxprice)
        self.ob_tape = []  # tape of just this orderbook's activities (may be consolidated at Exchange level)
        self.last_trans_t = None  # time of last transaction
        self.last_trans_p = None  # price of last transaction
        self.last_trans_q = None  # quantity of last transaction

    def __str__(self):
        s = 'Orderbook:\n'
        s = s + 'Bids: %s \n' % str(self.bids)
        s = s + 'Asks: %s \n' % str(self.asks)
        s = s + 'Tape[-5:]: %s \n' % str(self.ob_tape[-5:])
        s = s + '\n'
        return s

    def midprice(self, bid_p, bid_q, ask_p, ask_q):
        # returns midprice as mean of best bid and best ask if both best bid & best ask exist
        # if only one best price exists, returns that as mid
        # if neither best price exists, returns None
        mprice = None
        if bid_q > 0 and ask_q is None:
            mprice = bid_p
        elif ask_q > 0 and bid_q is None:
            mprice = ask_p
        elif bid_q > 0 and ask_q > 0:
            mprice = (bid_p + ask_p) / 2.0
        return mprice

    def microprice(self, bid_p, bid_q, ask_p, ask_q):
        mprice = None
        if bid_q > 0 and ask_q > 0:
            tot_q = bid_q + ask_q
            mprice = ((bid_p * ask_q) + (ask_p * bid_q)) / tot_q
        return mprice

    def add_lim_order(self, order, verbose):
        # add a LIM order to the LOB and update records
        if verbose:
            print('>add_lim_order: order.orderid=%d' % order.orderid)
        if order.otype == 'Bid':
            response = self.bids.book_add(order, verbose)
            best_price = self.bids.lob_anon[0][0]
            self.bids.best_price = best_price
        else:
            response = self.asks.book_add(order, verbose)
            best_price = self.asks.lob_anon[0][0]
            self.asks.best_price = best_price
        return response

    def process_order_CAN(self, time, order, verbose):

        # cancel an existing order
        if verbose:
            print('>Orderbook.process_order_CAN order.orderid=%d' % order.orderid)

        if order.otype == 'Bid':
            # cancel order from the bid book
            response = self.bids.book_CAN(time, order, self.idstr, verbose)
        elif order.otype == 'Ask':
            # cancel order from the ask book
            response = self.asks.book_CAN(time, order, self.idstr, verbose)
        else:
            # we should never get here
            sys.exit('process_order_CAN() given neither Bid nor Ask')

        # response should be a message for the trader, and an event to write to the tape

        if verbose:
            print('PO_CAN %s' % response)

        return response

    def process_order_XXX(self, time, order, verbose):

        # cancel all orders on this orderbook that were issued by the trader that issued this order
        if verbose:
            print('>Orderbook.process_order_XXX order.orderid=%d' % order.orderid)

        tid = order.tid
        # need to sweep through all bids and and all asks and delete all orders from this trader

        responselist = []

        for bid_order in self.bids.orders:
            if bid_order.tid == tid:
                responselist.append(self.bids.book_CAN(time, order, verbose))

        for ask_order in self.asks.orders:
            if ask_order.tid == tid:
                responselist.append(self.asks.book_CAN(time, order, verbose))

        # responselist is handed back to caller level for them to unpack

        if verbose:
            print('PO_CAN %s' % responselist)

        return responselist

    def process_order_take(self, time, order, verbose):

        if verbose:
            print('> Orderbook.process_order_take order.orderid=%d' % order.orderid)

        if order.otype == 'Bid':
            # this bid consumes from the top of the ask book
            response = self.asks.book_take(time, order, self.idstr, verbose)
        elif order.otype == 'Ask':
            # this ask consumes from the top of the bid book
            response = self.bids.book_take(time, order, self.idstr, verbose)
        else:  # we should never get here
            sys.exit('process_order_take() given neither Bid nor Ask')

        if verbose:
            print('OB.PO_take %s' % response)

        return response

    def process_order_LIM(self, time, order, verbose):

        # adds LIM and GFD orders -- GFD is just a time-limited LIM

        def process_LIM(lim_order, verbose):
            response = self.add_lim_order(lim_order, verbose)

            if verbose:
                print('>process_order_LIM order.orderid=%d' % lim_order.orderid)
                print('Response: %s' % response)

            return response

        oprice = order.price

        # does the LIM price cross the spread?

        if order.otype == 'Bid':
            if len(self.asks.lob) > 0 and oprice >= self.asks.lob[0][0]:
                # crosses: this LIM bid lifts the best ask, so treat as IOC
                if verbose:
                    print("Bid LIM $%s lifts best ask ($%s) =>IOC" % (oprice, self.asks.lob[0][0]))
                order.ostyle = 'IOC'
                response = self.process_order_take(time, order, verbose)
            else:
                response = process_LIM(order, verbose)

        elif order.otype == 'Ask':
            if len(self.bids.lob) > 0 and oprice <= self.bids.lob[0][0]:
                # crosses: this LIM ask hits the best bid, so treat as IOC
                if verbose:
                    print("Ask LIM $%s hits best bid ($%s) =>IOC" % (oprice, self.bids.lob[0][0]))
                order.ostyle = 'IOC'
                response = self.process_order_take(time, order, verbose)
            else:
                response = process_LIM(order, verbose)
        else:
            # we should never get here
            sys.exit('process_order_LIM() given neither Bid nor Ask')

        return response

    def process_order_pending(self, time, order, verbose):
        # this returns a null response because it just places the order on the relevant pending-execution list
        # order styles LOO and MOO are subsequently processed/executed in the market_open() method
        # order styles LOC and MOC are subsequently processed/executed in the market_close() method

        if verbose:
            print('process_order_pending>')

        if order.ostyle == 'LOO' or order.ostyle == 'MOO':
            if order.otype == 'Bid':
                self.bids.on_open.append(order)
            elif order.otype == 'Ask':
                self.asks.on_open.append(order)
            else:
                # we should never get here
                sys.exit('process_order_pending() LOO/MOO given neither Bid nor Ask')

        elif order.ostyle == 'LOC' or order.ostyle == 'MOC':
            if order.otype == 'Bid':
                self.bids.on_close.append(order)
            elif order.otype == 'Ask':
                self.asks.on_close.append(order)
            else:
                # we should never get here
                sys.exit('FAIL: process_order_pending() LOC/MOC given neither Bid nor Ask')

        else:
            sys.exit('FAIL: process_order_pending() given something other than LOO MOO LOC MOC')

        return {'TraderMsgs': None, 'TapeEvents': None}

    def process_order_OXO(self, time, order, verbose):
        # deals with OSO (one sends other) and OCO (one cancels other)
        # currently these are defined only in terms of LIM sub-orders
        # both these require the order to specify a PAIR of complete well-formed orders [OrderA, OrderB] in order.styleparams
        # if otype==OSO or OXO the rest of the top-level order is ignored, it's all down to what is in OrderA and OrderB
        # OrderB can itself be an OSO, and so on recursively -- so e.g. ICE is nested set of OSO orders.

        if order.ostyle == 'OCO':
            # one cancels the other
            dummy = 0
        elif order.ostyle == 'OSO':
            # one sends the other
            dummy = 0
        else:
            sys.exit('FAIL: process_order_OXO given neither OCO or OSO')

    def process_order_ICE(self, time, order, verbose):
        # sets up an iceberg order as a set of nested LIM OSOs.
        # order.styleparams needs to specify DisplayQty, which should be smaller than order.qty

        if order.ostyle == 'ICE':
            disp_qty = order.styleparams[DisplayQty]

            if disp_qty <= order.qty:
                # this is not a sensible ICE order
                sys.exit('FAIL in process_order_ICE(): order.qty=%d disp_qty=%d' % (order.qty, disp_qty))

            # first put together the final order in the chain
            final_qty = order.qty % disp_qty
            suborder_n = 0
            sub_id = str(order.orderid) + '-ice-' + str(suborder_n)
            if final_qty > 0:
                finalsuborder = Order(order.tid, order.otype, 'LIM', order.price, final_qty, order.time,
                                      order.endtime, sub_id)
            else:
                final_qty = disp_qty
                finalsuborder = Order(order.tid, order.otype, 'LIM', order.price, final_qty, order.time,
                                      order.endtime, sub_id)
            total_qty = final_qty

            suborder_n = suborder_n + 1
            sub_id = str(order.orderid) + '-ice-' + str(suborder_n)

            # pair that with another LIM order for disp_qty to form the first complete OSO pair
            disp_q_order = Order(order.tid, order.otype, 'LIM', order.price, disp_qty, order.time,
                                 order.endtime, sub_id)
            total_qty = total_qty + disp_qty

            # package the pair into the final OSO
            final_oso = Order(order.tid, order.otype, 'OSO', order.price, order.qty, order.time,
                              order.endtime, order.orderid)
            final_oso.styleparams = [disp_q_order, finalsuborder]

            previous_oso = final_oso

            # now continue to nest/embed inside further OSOs until total_qty matches order.qty
            while total_qty < order.qty:

                suborder_n = suborder_n + 1
                sub_id = str(order.orderid) + '-ice-' + str(suborder_n)

                disp_q_order = Order(order.tid, order.otype, 'LIM', order.price, disp_qty, order.time,
                                     order.endtime, sub_id)

                next_oso = Order(order.tid, order.otype, 'OSO', order.price, order.qty, order.time,
                                 order.endtime, order.orderid)
                next_oso.styleparams = [disp_q_order, previous_oso]

                total_qty = total_qty + disp_qty

                previous_oso = next_oso

            # at exit of the while loop, next_oso is the ICEberg fully converted into nested OSOs

            if verbose:
                print('process_order_ICE(): next_OSO = %s' % str(next_oso))

            # now that nested OSO itself needs to be processed.

            self.process_order_OXO(time, next_oso, verbose)


# Exchange's internal orderbooks

class Exchange(Orderbook):

    def __init__(self, eid):
        self.eid = eid  # exchange ID string
        self.lit = Orderbook(eid + "Lit")  # traditional lit exchange
        self.drk = Orderbook(eid + "Drk")  # NB just a placeholder -- in this version of BSE the dark pool is undefined
        self.tape = []  # tape: consolidated record of trading events on the exchange
        self.trader_recs = {}  # trader records (balances from fees, reputations, etc), indexed by traderID
        self.order_id = 0  # unique ID code for each order received by the exchange, starts at zero
        self.open = False  # is the exchange open (for business) or closed?

    def __str__(self):
        s = '\nExchID: %s ' % self.eid
        if self.open:
            s = s + '(Open)\n'
        else:
            s = s + '(Closed)\n'
        s = s + 'Lit ' + str(self.lit)
        s = s + 'Dark ' + str(self.drk)
        s = s + 'OID: %d; ' % self.order_id
        s = s + 'TraderRecs: %s' % self.trader_recs
        s = s + 'Tape[-4:]: %s' % self.tape[-4:]
        s = s + '\n'
        return s

    class trader_record:
        # exchange's records for an individual trader

        def __init__(self, time, tid):
            self.tid = tid  # this trader's ID
            self.regtime = time  # time when first registered
            self.balance = 0  # balance at the exchange (from exchange fees and rebates)
            self.reputation = None  # reputation -- FOR GEORGE CHURCH todo -- integrate with George's work
            self.orders = []  # list of orders received from this trader
            self.msgs = []  # list of messages sent to this trader

        def __str__(self):
            s = '[%s bal=%d rep=%s orders=%s msgs=%s]' % \
                (self.tid, self.balance, self.reputation, self.orders, self.msgs)
            return s

    def consolidate_responses(self, responses):

        consolidated = {'TraderMsgs': [], 'TapeEvents': []}

        if len(responses) > 1:
            # only need to do this if been given more than one response
            for resp in responses:
                consolidated['TraderMsgs'].append(resp['TraderMsgs'])
                consolidated['TapeEvents'].append(resp['TapeEvents'])
            # could sort into time-order here, but its not essential -- todo
        else:
            consolidated = responses[0]

        return consolidated

    def mkt_open(self, time, verbose):

        # exchange opens for business
        # need to process any LOO and MOO orders:
        # processes LOO and MOO orders in sequence wrt where they are in the relevant on_open list

        def open_pool(open_time, pool, verbose):

            responses = []

            # LOO and MOO
            for order in pool.on_open:
                if order.ostyle == 'LIM':
                    responses.append(pool.process_order_LIM(open_time, order, verbose))
                elif order.ostyle == 'MKT':
                    responses.append(pool.process_order_take(open_time, order, verbose))
                else:
                    sys.exit('FAIL in open_pool(): neither LIM nor MKT in on_open list ')

            return responses

        print('Exchange %s opening for business', self.eid)
        response_l = open_pool(time, self.lit, verbose)
        response_d = open_pool(time, self.drk, verbose)

        self.open = True
        return self.consolidate_responses([response_l, response_d])

    def mkt_close(self):

        # exchange closes for business
        # need to process any LOC, MOC, and GFD orders
        # NB GFD orders assumes that exchange closing is the same as end of day

        def close_pool(time, pool, verbose):

            responses = []

            # LOC and MOC
            for order in pool.on_close:
                if order.ostyle == 'LIM':
                    responses.append(pool.process_order_LIM(time, order, verbose))
                elif order.ostyle == 'MKT':
                    responses.append(pool.process_order_take(time, order, verbose))
                else:
                    sys.exit('FAIL in open_pool(): neither LIM nor MKT in on_close list ')
            # GFD  -- cancel any orders still on the books
            for order in pool.orders:
                if order.ostyle == 'GFD':
                    responses.append(pool.process_order_CAN(time, order, verbose))

            return responses

        print('Exchange %s closing for business', self.eid)
        response_l = close_pool(self.lit)
        response_d = close_pool(self.drk)

        self.open = False
        return self.consolidate_responses([response_l, response_d])

    def tape_update(self, tr, verbose):

        # updates the tape
        if verbose:
            print("Tape update: tr=%s; len(tape)=%d tape[-3:]=%s" % (tr, len(self.tape), self.tape[-3:]))

        self.tape.append(tr)

        if tr['type'] == 'Trade':
            # process the trade
            if verbose:
                print('>>>>>>>>TRADE t=%5.3f $%d Q%d %s %s\n' %
                      (tr['time'], tr['price'], tr['qty'], tr['party1'], tr['party2']))
            self.last_trans_t = tr['time']  # time of last transaction
            self.last_trans_p = tr['price']  # price of last transaction
            self.last_trans_q = tr['qty']  # quantity of last transaction
            return tr

    def dump_tape(self, session_id, dumpfile, tmode):

        print('Dumping tape s.tape=')
        for ti in self.tape:
            print('%s' % ti)

        for tapeitem in self.tape:
            print('tape_dump: tape_item=%s' % tapeitem)
            if tapeitem['type'] == 'Trade':
                dumpfile.write('%s, %s, %s, %s, %s\n' %
                               (session_id, tapeitem['pool_id'], tapeitem['time'], tapeitem['price'], str(tapeitem)))

        if tmode == 'wipe':
            self.tape = []

    def process_order(self, time, order, verbose):
        # process the order passed in as a parameter
        # number of allowable order-types is significantly expanded in BSE2 (previously just had LIM/MKT functionality)
        # BSE2 added order types such as FOK, ICE, etc
        # also added stub logic for larger orders to be routed to dark pool
        # currently treats dark pool as another instance of Orderbook, same as lit pool
        # incoming order has order ID assigned by exchange
        # return is {'tape_summary':... ,'trader_msgs':...}, explained further below

        if verbose:
            print('>Exchange.process_order()\n')

        trader_id = order.tid

        if trader_id not in self.trader_recs:
            # we've not seen this trader before, so create a record for it
            if verbose:
                print('t=%f: Exchange %s registering Trader %s:' % (time, self.eid, trader_id))
            trader_rec = self.trader_record(time, trader_id)
            self.trader_recs[trader_id] = trader_rec
            if verbose:
                print('record= %s' % str(trader_rec))

        # what quantity qualifies as a block trade (route to DARK)?
        block_size = 300

        ostyle = order.ostyle

        ack_response = ExchMsg(trader_id, order.orderid, 'ACK', [[order.price, order.qty]], None, 0, 0)
        if verbose:
            print(ack_response)

        # which pool does it get sent to: Lit or Dark?
        if order.qty < block_size:
            if verbose:
                print('Process_order: qty=%d routes to LIT pool' % order.qty)
            pool = self.lit
        else:
            if verbose:
                print('Process_order: qty=%d routes to DARK pool' % order.qty)
            pool = self.drk

        # Cancellations don't generate new order-ids

        if ostyle == 'CAN':
            # deleting a single existing order
            # NB this trusts the order.qty -- sends CANcel only to the pool that the QTY indicates
            response = pool.process_order_CAN(time, order, verbose)

        elif ostyle == 'XXX':
            # delete all orders from the trader that issued the XXX order
            # need to sweep through both pools
            response_l = self.lit.process_order_XXX(time, order, verbose)
            response_d = self.drk.process_order_XXX(time, order, verbose)
            # response from either lit and/or dark might be a string of responses from multiple individual CAN orders
            # here we just glue those together for later processing
            self.consolidate_responses([response_l, response_d])

        else:
            # give each new order a unique ID
            order.orderid = self.order_id
            self.order_id = order.orderid + 1

            ack_msg = ExchMsg(trader_id, order.orderid, 'ACK', [[order.price, order.qty]], None, 0, 0)

            if verbose:
                print('OrderID:%d, ack:%s\n' % (order.orderid, ack_msg))

            if ostyle == 'LIM' or ostyle == 'GFD':
                # GFD is just a LIM order with an expiry time
                response = pool.process_order_LIM(time, order, verbose)

            elif ostyle == 'MKT' or ostyle == 'AON' or ostyle == 'FOK' or ostyle == 'IOC':
                if ostyle == 'AON':
                    pool.resting.append(order)  # put it on the list of resting orders
                response = pool.process_order_take(time, order, verbose)
                # AON is a special case: if current response is that it FAILed, but has not timed out
                #                        then ignore the failure
                # and if it didn't fail, check to remove it from the MOB
                if ostyle == 'AON':
                    if response['TraderMsgs'].event == 'FAIL':
                        # it failed, but has it timed out yet?
                        if time < order.styleparams['ExpiryTime']:
                            # it hasn't expired yet
                            # nothing to say back to the trader, nothing to write to tape
                            response['TraderMsgs'] = None
                            response['TapeEvents'] = None
                    else:  # AON order executed successfully, remove it from the MOB
                        pool.resting.remove(order)

            elif ostyle == 'LOC' or ostyle == 'MOC' or ostyle == 'LOO' or ostyle == 'MOO':
                # these are just placed on the relevant wait-list at the exchange
                # and then processed by mkt_open() or mkt_close()
                response = pool.process_order_pending(time, order, verbose)

            elif ostyle == 'OCO' or ostyle == 'OSO':
                # processing of OSO and OCO orders is a recursive call of this method
                # that is, call process_order() on the first order in the OXO pair
                # then call or ignore the second order depending on outcome of the first
                # OCO and OSO are both defined via the following syntax...
                # ostyle=OSO or OCO; styleparams=[[order1], [order2]]
                # currently only defined for [order1] and [order2] both LIM type

                if len(order.styleparams) == 2:
                    order1 = order.styleparams[0]
                    order2 = order.styleparams[1]
                    if order1.ostyle == 'LIM' and order2.ostyle == 'LIM':
                        sys.exit('Give up')

                response = pool.process_order_OXO(time, order, verbose)

            elif ostyle == 'ICE':
                # this boils down to a chain of successively refreshed OSO orders, until its all used up
                # so underneath it's LIM functionality only
                response = pool.process_order_ICE(time, order, verbose)

            else:
                sys.exit('FAIL: process_order given order style %s', ostyle)

        if verbose:
            print ('<Exch.Proc.Order(): Order=%s; Response=%s' % (order, response))

        # default return values
        trader_msgs = None
        tape_events = None

        if response is not None:
            # non-null response should be dictionary with two items: list of trader messages and list of tape events
            if verbose:
                print('Response ---- ')
            trader_msgs = response["TraderMsgs"]
            tape_events = response["TapeEvents"]

            total_fees = 0
            # trader messages include details of fees charged by exchange for processing this order
            for msg in trader_msgs:
                if msg.tid == trader_id:
                    total_fees += msg.fee
                    if verbose:
                        print('Trader %s adding fee %d from msg %s' % (trader_id, msg.fee, msg))
            self.trader_recs[trader_id].balance += total_fees
            if verbose:
                print('Trader %s Exch %s: updated balance=%d' %
                      (trader_id, self.eid, self.trader_recs[trader_id].balance))

            # record the tape events on the tape
            if len(tape_events) > 0:
                for event in tape_events:
                    self.tape_update(event, verbose)

            if verbose:
                print('<Exch.Proc.Order(): tape_events=%s' % tape_events)
                s = '<Exch.Proc.Order(): trader_msgs=['
                for msg in trader_msgs:
                    s = s + '[' + str(msg) + '], '
                s = s + ']'
                print(s)

            # by this point, tape has been updated
            # so in principle only thing process_order hands back to calling level is messages for traders

            # but...

            # for back-compatibility with this method in BSE1.x and with trader definitions (AA, ZIP, etc)
            # we ALSO hand back a "transaction record" which summarises any actual transactions
            # or is None if no transactions occurred. Structure was:
            # transaction_record = {'type': 'Trade',
            #                       'time': time,
            #                       'price': price,
            #                       'party1': counterparty,
            #                       'party2': order.tid,
            #                       'qty': order.qty
            #                       }
            # In BSE 1.x the maximum order-size was Qty=1, which kept things very simple
            # In BSE 2.x, a single order of Qty>1 can result in multiple separate transactions,
            # so we need to aggregate those into one order. Do this by computing total cost C of
            # execution for quantity Q and then declaring that the price for each unit was C/Q
            # As there may now be more then one counterparty to a single order, party1 & party2 returned as None

            tape_summary = None
            if len(tape_events) > 0:
                total_cost = 0
                total_qty = 0
                if verbose:
                    print('tape_summary:')
                for event in tape_events:
                    if event['type'] == 'Trade':
                        total_cost += (event['price'] * event['qty'])
                        total_qty += event['qty']
                        if verbose:
                            print('total_cost=%d; total_qty=%d' % (total_cost, total_qty))
                if total_qty > 0:
                    avg_cost = total_cost / total_qty
                    if verbose:
                        print('avg_cost=%d' % avg_cost)
                    tape_summary = {'type': 'Trade',
                                    'time': time,
                                    'price': avg_cost,
                                    'party1': None,
                                    'party2': None,
                                    'qty': total_qty}

            return {'tape_summary': tape_summary, 'trader_msgs': trader_msgs}
        else:
            return {'tape_summary': None, 'trader_msgs': None}

    # this returns the LOB data "published" by the exchange,
    # only applies to the lit book -- dark pools aren't published
    def publish_lob(self, time, tape_depth, verbose):

        n_bids = len(self.lit.bids.orders)
        if n_bids > 0:
            best_bid_p = self.lit.bids.lob_anon[0][0]
        else:
            best_bid_p = None

        n_asks = len(self.lit.asks.orders)
        if n_asks > 0:
            best_ask_p = self.lit.asks.lob_anon[0][0]
        else:
            best_ask_p = None

        public_data = {}
        public_data['time'] = time
        public_data['bids'] = {'bestp': best_bid_p,
                               'worstp': self.lit.bids.worst_price,
                               'n': n_bids,
                               'lob': self.lit.bids.lob_anon}
        public_data['asks'] = {'bestp': best_ask_p,
                               'worstp': self.lit.asks.worst_price,
                               'n': n_asks,
                               'lob': self.lit.asks.lob_anon}

        public_data['last_t'] = self.lit.last_trans_t
        public_data['last_p'] = self.lit.last_trans_p
        public_data['last_q'] = self.lit.last_trans_q

        if tape_depth is None:
            public_data['tape'] = self.tape  # the full thing
        else:
            public_data['tape'] = self.tape[-tape_depth:]  # depth-limited

        public_data['midprice'] = None
        public_data['microprice'] = None
        if n_bids > 0 and n_asks > 0:
            # neither side of the LOB is empty
            best_bid_q = self.lit.bids.lob_anon[0][1]
            best_ask_q = self.lit.asks.lob_anon[0][1]
            public_data['midprice'] = self.lit.midprice(best_bid_p, best_bid_q, best_ask_p, best_ask_q)
            public_data['microprice'] = self.lit.microprice(best_bid_p, best_bid_q, best_ask_p, best_ask_q)

        if verbose:
            print('Exchange.publish_lob: t=%s' % time)
            print('BID_lob=%s' % public_data['bids']['lob'])
            print('best=%s; worst=%s; n=%s ' % (best_bid_p, self.lit.bids.worst_price, n_bids))
            print(str(self.lit.bids))
            print('ASK_lob=%s' % public_data['asks']['lob'])
            print('best=%s; worst=%s; n=%s ' % (best_ask_p, self.lit.asks.worst_price, n_asks))
            print(str(self.lit.asks))
            print('Midprice=%s; Microprice=%s' % (public_data['midprice'], public_data['microprice']))
            print('Last transaction: time=%s; price=%s; qty=%s' %
                  (public_data['last_t'], public_data['last_p'], public_data['last_q']))
            print('tape[-3:]=%s' % public_data['tape'][-3:])
            sys.stdout.flush()

        return public_data
