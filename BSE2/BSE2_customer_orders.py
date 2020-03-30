# -*- coding: utf-8 -*-
#
# BSE: The Bristol Stock Exchange
#
# Version 2.1Beta: Nov 20th, 2020.
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

# could import pylab here for graphing etc

import sys
import random

from BSE2_sys_consts import bse_sys_minprice, bse_sys_maxprice


from BSE2_msg_classes import Assignment


# customer_orders(): allocate orders to traders
# this version only issues LIM orders; LIM that crosses the spread executes as MKT
# parameter "os" is order schedule
# os['timemode'] is either 'periodic', 'drip-fixed', 'drip-jitter', or 'drip-poisson'
# os['interval'] is number of seconds for a full cycle of replenishment
# drip-poisson sequences will be normalised to ensure time of last replenishment <= interval
# parameter "pending" is the list of future orders (if this is empty, generates a new one from os)
# revised "pending" is the returned value
#
# also returns a list of "cancellations": trader-ids for those traders who are now working a new order and hence
# need to kill quotes already on LOB from working previous order
#
#
# if a supply or demand schedule mode is "random" and more than one range is supplied in ranges[],
# then each time a price is generated one of the ranges is chosen equiprobably and
# the price is then generated uniform-randomly from that range
#
# if len(range)==2, interpreted as min and max values on the schedule, specifying linear supply/demand curve
# if len(range)==3, first two vals are min & max, third value should be a function that generates a dynamic price offset
#                   -- the offset value applies equally to min & max, so gradient of linear sup/dem curve doesn't vary
# if len(range)==4, the third value is function that gives dynamic offset for schedule min,
#                   & 4th is a fn giving dynamic offset for schedule max, so gradient of sup/dem linear curve can vary
#
# the interface on this is a bit of a mess... could do with refactoring


def customer_orders(time, traders, trader_stats, os, pending, base_oid, verbose):

    def sysmin_check(price):
        if price < bse_sys_minprice:
            print('WARNING: price < bse_sys_min -- clipped')
            price = bse_sys_minprice
        return price

    def sysmax_check(price):
        if price > bse_sys_maxprice:
            print('WARNING: price > bse_sys_max -- clipped')

            price = bse_sys_maxprice
        return price

    def getorderprice(i, schedule_end, schedule, n, sch_mode, isstime):
        # does the first schedule range include optional dynamic offset function(s)?
        if len(schedule[0]) > 2:
            offsetfn = schedule[0][2][0]
            offsetfn_params = [schedule_end] + [p for p in schedule[0][2][1]]
            if callable(offsetfn):
                # same offset for min and max
                offset_min = offsetfn(isstime, offsetfn_params)
                offset_max = offset_min
            else:
                sys.exit('FAIL: 3rd argument of sched in getorderprice() should be [callable_fn [params]]')
            if len(schedule[0]) > 3:
                # if second offset function is specfied, that applies only to the max value
                offsetfn = schedule[0][3][0]
                offsetfn_params = [schedule_end] + [p for p in schedule[0][3][1]]
                if callable(offsetfn):
                    # this function applies to max
                    offset_max = offsetfn(isstime, offsetfn_params)
                else:
                    sys.exit('FAIL: 4th argument of sched in getorderprice() should be [callable_fn [params]]')
        else:
            offset_min = 0.0
            offset_max = 0.0

        pmin = sysmin_check(offset_min + min(schedule[0][0], schedule[0][1]))
        pmax = sysmax_check(offset_max + max(schedule[0][0], schedule[0][1]))
        prange = pmax - pmin
        stepsize = prange / (n - 1)
        halfstep = round(stepsize / 2.0)

        if sch_mode == 'fixed':
            ordprice = pmin + int(i * stepsize)
        elif sch_mode == 'jittered':
            ordprice = pmin + int(i * stepsize) + random.randint(-halfstep, halfstep)
        elif sch_mode == 'random':
            if len(sched) > 1:
                # more than one schedule: choose one equiprobably
                s = random.randint(0, len(sched) - 1)
                pmin = sysmin_check(min(schedule[s][0], schedule[s][1]))
                pmax = sysmax_check(max(schedule[s][0], schedule[s][1]))
            ordprice = random.randint(pmin, pmax)
        else:
            sys.exit('FAIL: Unknown mode in schedule')
        ordprice = sysmin_check(sysmax_check(ordprice))
        return ordprice

    def getissuetimes(n_traders, tmode, interval, shuffle, fittointerval):
        # generates a set of issue times for the customer orders to arrive at
        interval = float(interval)
        if n_traders < 1:
            sys.exit('FAIL: n_traders < 1 in getissuetime()')
        elif n_traders == 1:
            tstep = interval
        else:
            tstep = interval / (n_traders - 1)
        arrtime = 0
        isstimes = []
        for trdr in range(n_traders):
            if tmode == 'periodic':
                arrtime = interval
            elif tmode == 'drip-fixed':
                arrtime = trdr * tstep
            elif tmode == 'drip-jitter':
                arrtime = trdr * tstep + tstep * random.random()
            elif tmode == 'drip-poisson':
                # poisson requires a bit of extra work
                interarrivaltime = random.expovariate(n_traders / interval)
                arrtime += interarrivaltime
            else:
                sys.exit('FAIL: unknown time-mode in getissuetimes()')
            isstimes.append(arrtime)

            # at this point, arrtime is the *last* arrival time
        if fittointerval and tmode == 'drip-poisson' and (arrtime != interval):
            # generated sum of interarrival times longer than the interval
            # squish them back so that last arrival falls at t=interval
            for trdr in range(n_traders):
                isstimes[trdr] = interval * (isstimes[trdr] / arrtime)

        # optionally randomly shuffle the times
        if shuffle:
            for trdr in range(n_traders):
                i = (n_traders - 1) - trdr
                j = random.randint(0, i)
                tmp = isstimes[i]
                isstimes[i] = isstimes[j]
                isstimes[j] = tmp
        return isstimes

    def getschedmode(current_time, order_schedules):
        got_one = False
        schedrange = None
        sch_mode = None
        sched_end_time = None
        for sch in order_schedules:
            if (not got_one) and (sch['from'] <= current_time) and (current_time < sch['to']):
                # within the timezone for this schedule
                schedrange = sch['ranges']
                sch_mode = sch['stepmode']
                sched_end_time = sch['to']
                got_one = True  # the first matching timezone has priority over any others
        if not got_one:
            sys.exit('Fail: time=%5.2f not within any timezone in os=%s' % (current_time, os))
        return schedrange, sch_mode, sched_end_time

    n_buyers = trader_stats['n_buyers']
    n_sellers = trader_stats['n_sellers']

    shuffle_times = True

    cancellations = []

    oid = base_oid

    max_qty = 1

    if len(pending) < 1:
        # list of pending (to-be-issued) customer orders is empty, so generate a new one
        new_pending = []

        # demand side (buyers)
        issuetimes = getissuetimes(n_buyers, os['timemode'], os['interval'], shuffle_times, True)
        ordertype = 'Bid'
        orderstyle = 'LIM'
        (sched, mode, sched_end) = getschedmode(time, os['dem'])
        for t in range(n_buyers):
            issuetime = time + issuetimes[t]
            tname = 'B%02d' % t
            orderprice = getorderprice(t, sched_end, sched, n_buyers, mode, issuetime)
            orderqty = random.randint(1, max_qty)
            # order = Order(tname, ordertype, orderstyle, orderprice, orderqty, issuetime, None, oid)
            order = Assignment("CUS", tname, ordertype, orderstyle, orderprice, orderqty, issuetime, None, oid)
            oid += 1
            new_pending.append(order)

        # supply side (sellers)
        issuetimes = getissuetimes(n_sellers, os['timemode'], os['interval'], shuffle_times, True)
        ordertype = 'Ask'
        orderstyle = 'LIM'
        (sched, mode, sched_end) = getschedmode(time, os['sup'])
        for t in range(n_sellers):
            issuetime = time + issuetimes[t]
            tname = 'S%02d' % t
            orderprice = getorderprice(t, sched_end, sched, n_sellers, mode, issuetime)
            orderqty = random.randint(1, max_qty)
            # order = Order(tname, ordertype, orderstyle, orderprice, orderqty, issuetime, None, oid)
            order = Assignment("CUS", tname, ordertype, orderstyle, orderprice, orderqty, issuetime, None, oid)
            oid += 1
            new_pending.append(order)
    else:
        # there are pending future orders: issue any whose timestamp is in the past
        new_pending = []
        for order in pending:
            if order.time < time:
                # this order should have been issued by now
                # issue it to the trader
                tname = order.trad_id
                response = traders[tname].add_cust_order(order, verbose)
                if verbose:
                    print('Customer order: %s %s' % (response, order))
                if response == 'LOB_Cancel':
                    cancellations.append(tname)
                    if verbose:
                        print('Cancellations: %s' % cancellations)
                # and then don't add it to new_pending (i.e., delete it)
            else:
                # this order stays on the pending list
                new_pending.append(order)
    return [new_pending, cancellations, oid]
