import sys
import random
from TBSE_msg_classes import Order
from TBSE_sys_consts import tbse_sys_maxprice, tbse_sys_minprice


# Mostly unaltered from original BSE code by Dave Cliff
def customer_orders(time, coid, last_update, traders, trader_stats, os, pending, verbose):

        def sysmin_check(price):
            if price < tbse_sys_minprice:
                print('WARNING: price < bse_sys_min -- clipped')
                price = tbse_sys_minprice
            return price


        def sysmax_check(price):
            if price > tbse_sys_maxprice:
                print('WARNING: price > bse_sys_max -- clipped')
                price = tbse_sys_maxprice
            return price

        

        def getorderprice(i, sched, n, mode, issuetime):
            # does the first schedule range include optional dynamic offset function(s)?
            if len(sched[0]) > 2:
                offsetfn = sched[0][2]
                if callable(offsetfn):
                    # same offset for min and max
                    offset_min = offsetfn(issuetime)
                    offset_max = offset_min
                else:
                    sys.exit('FAIL: 3rd argument of sched in getorderprice() not callable')
                if len(sched[0]) > 3:
                    # if second offset function is specfied, that applies only to the max value
                    offsetfn = sched[0][3]
                    if callable(offsetfn):
                        # this function applies to max
                        offset_max = offsetfn(issuetime)
                    else:
                        sys.exit('FAIL: 4th argument of sched in getorderprice() not callable')
            else:
                offset_min = 0.0
                offset_max = 0.0

            pmin = sysmin_check(offset_min + min(sched[0][0], sched[0][1]))
            pmax = sysmax_check(offset_max + max(sched[0][0], sched[0][1]))
            prange = pmax - pmin
            stepsize = prange / (n - 1)
            halfstep = round(stepsize / 2.0)

            if mode == 'fixed':
                orderprice = pmin + int(i * stepsize) 
            elif mode == 'jittered':
                orderprice = pmin + int(i * stepsize) + random.randint(-halfstep, halfstep)
            elif mode == 'random':
                if len(sched) > 1:
                    # more than one schedule: choose one equiprobably
                    s = random.randint(0, len(sched) - 1)
                    pmin = sysmin_check(min(sched[s][0], sched[s][1]))
                    pmax = sysmax_check(max(sched[s][0], sched[s][1]))
                orderprice = random.randint(pmin, pmax)
            else:
                sys.exit('FAIL: Unknown mode in schedule')
            orderprice = sysmin_check(sysmax_check(orderprice))
            return orderprice



        def getissuetimes(n_traders, mode, interval, shuffle, fittointerval):

            interval = float(interval)
            if n_traders < 1:
                sys.exit('FAIL: n_traders < 1 in getissuetime()')
            elif n_traders == 1:
                tstep = interval
            else:
                tstep = interval / (n_traders - 1)
            arrtime = 0
            issuetimes = []
            for t in range(n_traders):
                if mode == 'periodic':
                    arrtime = interval
                elif mode == 'drip-fixed':
                    arrtime = t * tstep
                elif mode == 'drip-jitter':
                    arrtime = t * tstep + tstep * random.random()
                elif mode == 'drip-poisson':
                    # poisson requires a bit of extra work
                    interarrivaltime = random.expovariate(n_traders / interval)
                    arrtime += interarrivaltime
                else:
                    sys.exit('FAIL: unknown time-mode in getissuetimes()')
                issuetimes.append(arrtime) 
                
            # at this point, arrtime is the last arrival time
            if fittointerval and ((arrtime > interval) or (arrtime < interval)):
                # generated sum of interarrival times longer than the interval
                # squish them back so that last arrival falls at t=interval
                for t in range(n_traders):
                    issuetimes[t] = interval * (issuetimes[t] / arrtime)
            # optionally randomly shuffle the times
            if shuffle:
                for t in range(n_traders):
                    i = (n_traders - 1) - t
                    j = random.randint(0, i)
                    tmp = issuetimes[i]
                    issuetimes[i] = issuetimes[j]
                    issuetimes[j] = tmp
            return issuetimes
        

        def getschedmode(time, os):
            got_one = False
            for sched in os:
                if (sched['from'] <= time) and (time < sched['to']) :
                    # within the timezone for this schedule
                    schedrange = sched['ranges']
                    mode = sched['stepmode']
                    got_one = True
                    exit  # jump out the loop -- so the first matching timezone has priority over any others
            if not got_one:
                sys.exit('Fail: time=%5.2f not within any timezone in os=%s' % (time, os))
            return (schedrange, mode)
    

        n_buyers = trader_stats['n_buyers']
        n_sellers = trader_stats['n_sellers']

        shuffle_times = True

        cancellations = []

        if len(pending) < 1:
            # list of pending (to-be-issued) customer orders is empty, so generate a new one
            new_pending = []

            # demand side (buyers)
            issuetimes = getissuetimes(n_buyers, os['timemode'], os['interval'], shuffle_times, True)
            ordertype = 'Bid'
            (sched, mode) = getschedmode(time, os['dem'])             
            for t in range(n_buyers):
                issuetime = time + issuetimes[t]
                tname = 'B%02d' % t
                orderprice = getorderprice(t, sched, n_buyers, mode, issuetime)
                order = Order(tname, ordertype, orderprice, 1, issuetime, coid, -3.14)
                new_pending.append(order) 
                coid += 1
                    
            # supply side (sellers)
            issuetimes = getissuetimes(n_sellers, os['timemode'], os['interval'], shuffle_times, True)
            ordertype = 'Ask'
            (sched, mode) = getschedmode(time, os['sup'])
            for t in range(n_sellers):
                issuetime = time + issuetimes[t]
                tname = 'S%02d' % t
                orderprice = getorderprice(t, sched, n_sellers, mode, issuetime)
                order = Order(tname, ordertype, orderprice, 1, issuetime, coid, -3.14)
                new_pending.append(order)
                coid += 1
        else:
            # there are pending future orders: issue any whose timestamp is in the past
            new_pending = []
            for order in pending:
                if order.time < time:
                    # this order should have been issued by now
                    # issue it to the trader
                    tname = order.tid
                    response = traders[tname].add_order(order, verbose)
                    if verbose: print('Customer order: %s %s' % (response, order) )
                    if response == 'LOB_Cancel' :
                        cancellations.append(tname)
                        if verbose: print('Cancellations: %s' % (cancellations))
                    # and then don't add it to new_pending (i.e., delete it)
                else:
                    # this order stays on the pending list
                    new_pending.append(order)
        return [new_pending, cancellations, coid]

