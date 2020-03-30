# -*- coding: utf-8 -*-
#
# BSE: The Bristol Stock Exchange
#
# Version 2.0Beta: Nov 20th, 2018.
# Version 1.4: August 30th, 2018.
# Version 1.3: July 21st, 2018.
# Version 1.2: November 17th, 2012.
#
# Copyright (c) 2012-2019, Dave Cliff
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

# could import pylab here for graphing etc

import sys
# import math
import random
# import csv
# from datetime import datetime

# import matplotlib.pyplot as plt
# import numpy as np

# from BSE2_msg_classes import Assignment, Order, ExchMsg
from BSE2_exchange import Exchange
from BSE2_trader_agents import trader_create
from BSE2_customer_orders import customer_orders

# from BSE2_unittests import test_all
# from BSE2_dev import proc_OXO proc_ICE


class Entity:

    def __init__(self, id, init_balance, init_reputation, traders):
        self.lei = id  # LEI = legal entity identifier
        self.balance = init_balance
        self.reputation = init_reputation
        self.traders = traders

    def __str__(self):
        s = '[%s $%d R=%d %s]' % (self.lei, self.balance, self.reputation, str(self.traders))
        return s



# #########################---Below lies the experiment/test-rig---##################


# trade_stats()
# dump CSV statistics on exchange data and trader population to file for later analysis
# this makes no assumptions about the number of types of traders, or
# the number of traders of any one type -- allows either/both to change
# between successive calls, but that does make it inefficient as it has to
# re-analyse the entire set of traders on each call
def trade_stats(expid, traders, dumpfile, time, lob):
    trader_types = {}
    for t in traders:
        ttype = traders[t].ttype
        if ttype in trader_types.keys():
            t_balance = trader_types[ttype]['balance_sum'] + traders[t].balance
            n = trader_types[ttype]['n'] + 1
        else:
            t_balance = traders[t].balance
            n = 1
        trader_types[ttype] = {'n': n, 'balance_sum': t_balance}

    dumpfile.write('%s, %06d, ' % (expid, time))
    for ttype in sorted(list(trader_types.keys())):
        n = trader_types[ttype]['n']
        s = trader_types[ttype]['balance_sum']
        dumpfile.write('%s, %d, %d, %f, ' % (ttype, s, n, s / float(n)))

    if lob['bids']['bestp'] is not None:
        dumpfile.write('%d, ' % (lob['bids']['bestp']))
    else:
        dumpfile.write('N, ')
    if lob['asks']['bestp'] is not None:
        dumpfile.write('%d, ' % (lob['asks']['bestp']))
    else:
        dumpfile.write('N, ')
    dumpfile.write('\n')


# create a bunch of traders from traders_specification, links them to the relevant entities
# returns tuple (n_buyers, n_sellers)
# optionally shuffles the pack of buyers and the pack of sellers
def populate_market(entities, traders_specification, traders, shuffle, verbose):

    def shuffle_traders(ttype_char, n, shuff_traders):
        for swap in range(n):
            t1 = (n - 1) - swap
            t2 = random.randint(0, t1)
            t1name = '%c%02d' % (ttype_char, t1)
            t2name = '%c%02d' % (ttype_char, t2)
            shuff_traders[t1name].tid = t2name
            shuff_traders[t2name].tid = t1name
            temp = traders[t1name]
            shuff_traders[t1name] = shuff_traders[t2name]
            shuff_traders[t2name] = temp

    n_buyers = 0
    for bs in traders_specification['buyers']:
        ttype = bs[0]
        for b in range(bs[1]):
            tname = 'B%02d' % n_buyers  # buyer i.d. string
            traders[tname] = trader_create('NoLEI', ttype, tname)
            n_buyers = n_buyers + 1

    if n_buyers < 1:
        sys.exit('FATAL: no buyers specified\n')

    if shuffle:
        shuffle_traders('B', n_buyers, traders)

    n_sellers = 0
    for ss in traders_specification['sellers']:
        ttype = ss[0]
        for s in range(ss[1]):
            tname = 'S%02d' % n_sellers  # buyer i.d. string
            traders[tname] = trader_create('NoLEI', ttype, tname)
            n_sellers = n_sellers + 1

    if n_sellers < 1:
        sys.exit('FATAL: no sellers specified\n')

    if shuffle:
        shuffle_traders('S', n_sellers, traders)

    if verbose:
        print('>populate_market()')
        for e in entities: print(e)
        for t in range(n_buyers):
            bname = 'B%02d' % t
            print(traders[bname])
        for t in range(n_sellers):
            bname = 'S%02d' % t
            print(traders[bname])

    return {'n_buyers': n_buyers, 'n_sellers': n_sellers}


# one session in the market
def market_session(session_id, starttime, endtime, entities, trader_spec, order_schedule, summaryfile, tapedumpfile,
                   blotterdumpfile, verbose):

    def blotterdump(all_traders, blotdumpfile):
        # traders dump their blotters
        for tr in all_traders:
            trader_id = all_traders[tr].tid
            ttype = all_traders[tr].ttype
            balance = all_traders[tr].balance
            blot = all_traders[tr].blotter
            blot_len = len(blot)
            # build csv string for all events in blotter
            csv = ''
            for b in blot:
                csv = csv + '\"%s\", %s, ' % (str(b[0]), b[1])
            blotdumpfile.write(
                '%s, %s, %s, %s, %s, %s\n' % (session_id, trader_id, ttype, balance, blot_len, csv))

    def process_kills(kill_list, all_traders, verboseness):
        # if any newly-issued customer orders means any trader's quotes on the LOB need to be cancelled, kill them
        if len(kill_list) > 0:
            if verboseness:
                print('Kills: %s' % kill_list)
            for kill in kill_list:
                # if verbosity: print('lastquote=%s' % traders[kill].lastquote)
                if all_traders[kill].lastquote is not None:
                    if verboseness:
                        print('Killing order %s' % (str(all_traders[kill].lastquote)))

                    cancel_order = all_traders[kill].lastquote
                    cancel_order.ostyle = "CAN"
                    exchange_response = exchanges[0].process_order(time, cancel_order, process_verbose)
                    exchange_msg = exchange_response['trader_msgs']
                    # do the necessary book-keeping
                    # NB this assumes CAN results in a single message back from the exchange
                    all_traders[kill].bookkeep(exchange_msg[0], time, bookkeep_verbose)

    def get_pub_lobs(all_exchanges):
        # get the published lobs from each exchange
        all_lobs = []
        for this_exchange in all_exchanges:
            this_lob = this_exchange.publish_lob(time, tape_depth, lob_verbose)
            if verbose:
                print('Exchange %s, Published LOB=%s' % (this_exchange, str(this_lob)))
            all_lobs.append(this_lob)
        return all_lobs

    def rand_tid(trader_id, all_traders):
        # randomly choose a trader id that is different from the trader_id parameter
        new_id = trader_id
        while new_id == trader_id:
            new_id = list(all_traders.keys())[random.randint(0, len(all_traders) - 1)]
        return new_id

    def prices_dump(dump_time, all_traders, prices_file, verboseness):
        # write data-file of the prices currently being quoted by the traders

        if dump_time == 0:
            # print column headers
            s = '0.0, '
            for tr in all_traders:
                s = s + '%s,' % all_traders[tr].tid
            prices_file.write('%s\n' % s)
        else:
            s = '%6.2f, ' % dump_time
            for tr in all_traders:
                # to select certain trader types replace "if Ture" with things like...
                # --> if traders[t].ttype == 'ISHV':
                if True:
                    lq = all_traders[tr].lastquote
                    if verboseness:
                        print('lq = %s' % lq)
                    if lq is not None:
                        price = lq.price
                    else:
                        price = None
                    if price is None:
                        s = s + '-1, '
                    else:
                        s = s + '%s, ' % price
            prices_file.write('%s\n' % s)

    def sanity_check(price, check_order):
        # this simply bails via sys.exit() if things are not right
        if check_order.otype == 'Ask' and check_order.price < price:
            sys.exit('Bad ask: Trader.price %s, Quote: %s' % (price, check_order))
        if check_order.otype == 'Bid' and check_order.price > price:
            sys.exit('Bad bid: Trader.price %s, Quote: %s' % (price, check_order))

    n_exchanges = 1

    tape_depth = 5  # number of most-recent items from tail of tape to be published at any one time

    verbosity = True

    verbose = verbosity  # main loop verbosity
    orders_verbose = verbosity
    lob_verbose = True
    process_verbose = True
    respond_verbose = True
    bookkeep_verbose = True

    price_fname = session_id + 'prices.csv'
    prices_data_file = open(price_fname, 'w')


    # initialise the exchanges
    exchanges = []
    for e in range(n_exchanges):
        eid = "Exch%d" % e
        exch = Exchange(eid)
        exchanges.append(exch)
        if verbose:
            print('Exchange[%d] =%s' % (e, str(exchanges[e])))


    # create a bunch of traders
    traders = {}
    trader_stats = populate_market(entities, trader_spec, traders, True, verbose)


    # assign traders to entities: currently done on a one-to-one mapping; barf if mismatch
    # this code is VERY specific -- needs refactoring to make it more generic
    if len(traders) != len(entities):
        sys.stdout.flush()
        sys.exit('FAIL: #traders doesn\'t match #entities in market_session()')
    else:
        e = 0
        sys.stdout.flush()
        for trader in traders:
            entities[e].traders=[trader]
            traders[trader].lei = entities[e].lei
            e += 1

    #show what we've got
    if verbose:
        for e in entities:
            print(e)
            for t in e.traders:
                print(traders[t])

    # timestep set so that can process all entities in one second
    # NB minimum inter-arrival time of customer orders may be much less than this!!
    timestep = 1.0 / float(trader_stats['n_buyers'] + trader_stats['n_sellers'])

    session_duration = float(endtime - starttime)

    time = starttime

    next_order_id = 0

    pending_cust_orders = []

    if verbose:
        print('\n%s;  ' % session_id)

    tid = None

    while time < endtime:

        if time == starttime:
            prices_dump(time, traders, prices_data_file, verbose)

        # how much time left, as a percentage?
        time_left = (endtime - time) / float(session_duration)
        if verbose:
            print('\n\n%s; t=%08.2f (percent remaining: %4.1f/100) ' % (session_id, time, time_left * 100))

        # trade = None

        # get any new assignments (customer orders) for traders to execute
        # and also any customer orders that require previous orders to be killed -- kills is list of trader-IDs
        [pending_cust_orders, kills, noid] = customer_orders(time, traders, trader_stats,
                                                             order_schedule, pending_cust_orders, next_order_id,
                                                             orders_verbose)

        next_order_id = noid

        if verbose:
            print('t:%f, noid=%d, pending_cust_orders:' % (time, noid))
            for order in pending_cust_orders:
                print('%s; ' % str(order))

        # if any newly-issued customer orders means any trader's quotes on the LOB need to be cancelled, kill them
        process_kills(kills, traders, verbose)

        if verbose:
            for t in traders:
                if len(traders[t].orders) > 0:
                    print("Time=%5.2d TID=%s Orders[0]=%s" % (time, traders[t].tid, traders[t].orders[0]))

        # get public lob data from each exchange
        lobs = get_pub_lobs(exchanges)

        # first randomly select a trader id (different from the last one)
        tid = rand_tid(tid, traders)

        # get an order from that trader
        order = traders[tid].getorder(time, time_left, lobs[0], verbose)

        if verbose:
            print('Trader Order: %s' % str(order))

        # currently, all quotes/orders are issued only to the single exchange at exchanges[0]
        # it is that exchange's responsibility to then deal with Order Protection / trade-through (cf Reg NMS Rule611)
        # i.e. the exchange logic could/should be extended to check the best LOB price of each other exchange
        # that is yet to be implemented in this version

        if order is not None:

            order.myref = traders[tid].orders[0].assignmentid  # attach customer order ID to this exchange order
            if verbose:
                print('Order with myref=%s' % order.myref)

            # Sanity check: catch bad traders here (if anything wrong, calls sys.exit)
            sanity_check(traders[tid].orders[0].price, order)

            # how many quotes does this trader already have sat on an exchange?
            if len(traders[tid].quotes) >= traders[tid].max_quotes:
                # need to clear a space on the trader's list of quotes, by deleting one
                # new quote replaces trader's oldest previous quote
                # bit of a  kludge -- just deletes oldest quote, which is at head of list
                # THIS SHOULD BE IN TRADER NOT IN MAIN LOOP?? TODO
                can_order = traders[tid].quotes[0]
                if verbose:
                    print('> can_order %s' % str(can_order))
                can_order.ostyle = "CAN"
                if verbose:
                    print('> can_order %s' % str(can_order))

                # send cancellation to exchange
                exch_response = exchanges[0].process_order(time, can_order, process_verbose)
                exch_msg = exch_response['trader_msgs']
                #  tape_sum = exch_response['tape_summary']

                if verbose:
                    print('>Exchanges[0]ProcessOrder: tradernquotes=%d, quotes=[' % len(traders[tid].quotes))
                    for q in traders[tid].quotes:
                        print('%s' % str(q))
                    print(']')

                    '''
                    for t in traders:
                        if len(traders[t].orders) > 0:
                            print(">Exchanges[0]ProcessOrder: Tyme=%5.2d TID=%s Orders[0]=%s" % 
                                  (time, traders[t].tid, traders[t].orders[0]))
                        if len(traders[t].quotes) > 0:
                            print(">Exchanges[0]ProcessOrder: Tyme=%5.2d TID=%s Quotes[0]=%s" % 
                                  (time, traders[t].tid, traders[t].quotes[0]))
                    '''

                # do the necessary book-keeping
                # NB this assumes CAN results in a single message back from the exchange
                traders[tid].bookkeep(exch_msg[0], time, bookkeep_verbose)

            if verbose:
                # print('post-check: tradernquotes=%d, quotes=[' % len(traders[tid].quotes))
                for q in traders[tid].quotes:
                    print('%s' % str(q))
                print(']')
                for t in traders:
                    '''
                    if len(traders[t].orders) > 0:
                        # print("PostCheck Tyme=%5.2d TID=%s Orders[0]=%s" %
                        #      (time, traders[t].tid, traders[t].orders[0]))
                        if len(traders[t].quotes) > 0:
                            # print("PostCheck Tyme=%5.2d TID=%s Quotes[0]=%s" %
                            #      (time, traders[t].tid, traders[t].quotes[0]))
                            nop = 0
                    '''

                    if len(traders[t].orders) > 0 and traders[t].orders[0].astyle == "CAN":
                        sys.stdout.flush()
                        sys.exit('CAN error')

            # add order to list of live orders issued by this trader
            traders[tid].quotes.append(order)

            if verbose:
                print('Trader %s quotes[-1]: %s' % (tid, traders[tid].quotes[-1]))

            # send this order to exchange and receive response
            exch_response = exchanges[0].process_order(time, order, process_verbose)
            exch_msgs = exch_response['trader_msgs']
            tape_sum = exch_response['tape_summary']

            # because the order just processed might have changed things, now go through each
            # order resting at the exchange and see if it can now be processed
            # applies to AON, ICE, OSO, and OCO

            if verbose:
                print('Exch_Msgs: ')
                if exch_msgs is None:
                    print('None')
                else:
                    for msg in exch_msgs:
                        print('Msg=%s' % msg)

            if (exch_msgs is not None) and len(exch_msgs) > 0:
                # messages to process
                for msg in exch_msgs:
                    if verbose:
                        print('Message: %s' % msg)
                    traders[msg.tid].bookkeep(msg, time, bookkeep_verbose)

            # traders respond to whatever happened
            # needs to be updated for multiple exchanges
            lob = exchanges[0].publish_lob(time, tape_depth, lob_verbose)

            # NB respond() only updates trader's internal variables, it doesn't alter the LOB,
            # so processing each trader in sequence (rather than random/shuffle) isn't a problem
            for t in traders:
                traders[t].respond(time, lob, tape_sum, respond_verbose)

            # record prices quoted by each trader at this timestep
            prices_dump(time, traders, prices_data_file, verbose)

        time = time + timestep

    # end of an experiment

    # close the prices file
    prices_data_file.close()

    # dump the tape
    exchanges[0].dump_tape(session_id, tapedumpfile, 'keep')

    # traders dump their blotters
    blotterdump(traders, blotterdumpfile)

    # write summary trade_stats for this experiment (end-of-session summary ONLY)
    for e in range(n_exchanges):
        trade_stats(session_id, traders, summaryfile, time, exchanges[e].publish_lob(time, None, lob_verbose))


#############################

# # Below here is where we set up and run a series of experiments


if __name__ == "__main__":

    verbose = True

    start_time = 0.0
    end_time = 200.0
    # end_time=25200 # 7 hours x 60 min x 60 sec /
    duration = end_time - start_time

    # range1 = (95, 95, [bronco_schedule_offsetfn, [] ] )
    # range1 = (50, 150)
    range1 = (50, 50)
    supply_schedule = [{'from': start_time, 'to': end_time, 'ranges': [range1], 'stepmode': 'fixed'}]

    # range1 = (105, 105, [bronco_schedule_offsetfn, [] ] )
    # range1 = (50, 150)
    range1 = (150, 150)
    demand_schedule = [{'from': start_time, 'to': end_time, 'ranges': [range1], 'stepmode': 'fixed'}]

    order_sched = {'sup': supply_schedule, 'dem': demand_schedule,
                   'interval': 20,
                   'timemode': 'drip-poisson'}
    # 'timemode': 'periodic'}

    buyers_spec = [('ZIP', 10)]
    sellers_spec = buyers_spec
    traders_spec = {'sellers': sellers_spec, 'buyers': buyers_spec}

    total_traders = 0
    for spec in buyers_spec:
        total_traders += spec[1]
    for spec in sellers_spec:
        total_traders += spec[1]
    print('Total number of traders/entities is %d' % total_traders)

    # set up enough entities for a one-to-one mapping from traders to entities
    entities = []
    for e in range(total_traders):
        lei = 'LEI%03d' % e
        print(lei)
        e = Entity(lei, 100, 0, [])
        entities.append(e)
        if verbose:
            print(e)

    sys.stdout.flush()

    for session in range(1):
        sess_id = 'Test%02d' % session
        print('Session %s; ' % sess_id)

        bal_fname = sess_id + 'balances.csv'
        summary_data_file = open(bal_fname, 'w')

        tape_fname = sess_id + 'tapes.csv'
        tape_data_file = open(tape_fname, 'w')

        blot_fname = sess_id + 'blotters.csv'
        blotter_data_file = open(blot_fname, 'w')

        market_session(sess_id, start_time, end_time, entities, traders_spec, order_sched, summary_data_file, tape_data_file,
                       blotter_data_file, True)

    print('\n Experiment Finished')
