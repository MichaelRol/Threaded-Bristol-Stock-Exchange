import random
import sys

import config
from TBSE_msg_classes import Order
from TBSE_sys_consts import tbse_sys_max_price, tbse_sys_min_price


# Mostly unaltered from original BSE code by Dave Cliff
def customer_orders(time, coid, traders, trader_stats, os, pending, verbose):
    def sys_min_check(price):
        if price < tbse_sys_min_price:
            print('WARNING: price < bse_sys_min -- clipped')
            price = tbse_sys_min_price
        return price

    def sys_max_check(price):
        if price > tbse_sys_max_price:
            print('WARNING: price > bse_sys_max -- clipped')
            price = tbse_sys_max_price
        return price

    def get_order_price(i, sched, sched_end, n, mode, issue_time):
        if config.useInputFile:
            if len(sched[0]) > 2:
                offset_function = sched[0][2][0]
                offset_function_params = [sched_end] + [p for p in sched[0][2][1]]
                if callable(offset_function):
                    # same offset for min and max
                    offset_min = offset_function(issue_time, offset_function_params)
                    offset_max = offset_min
                else:
                    sys.exit('FAIL: 3rd argument of sched in get_order_price() should be [callable_fn [params]]')
                if len(sched[0]) > 3:
                    # if second offset function is specfied, that applies only to the max value
                    offset_function = sched[0][3][0]
                    offset_function_params = [sched_end] + [p for p in sched[0][3][1]]
                    if callable(offset_function):
                        # this function applies to max
                        offset_max = offset_function(issue_time, offset_function_params)
                    else:
                        sys.exit('FAIL: 4th argument of sched in get_order_price() should be [callable_fn [params]]')
            else:
                offset_min = 0.0
                offset_max = 0.0
        else:
            # does the first schedule range include optional dynamic offset function(s)?
            if len(sched[0]) > 2:
                offset_function = sched[0][2]
                if callable(offset_function):
                    # same offset for min and max
                    offset_min = offset_function(issue_time)
                    offset_max = offset_min
                else:
                    sys.exit('FAIL: 3rd argument of sched in get_order_price() not callable')
                if len(sched[0]) > 3:
                    # if second offset function is specfied, that applies only to the max value
                    offset_function = sched[0][3]
                    if callable(offset_function):
                        # this function applies to max
                        offset_max = offset_function(issue_time)
                    else:
                        sys.exit('FAIL: 4th argument of sched in get_order_price() not callable')
            else:
                offset_min = 0.0
                offset_max = 0.0

        p_min = sys_min_check(offset_min + min(sched[0][0], sched[0][1]))
        p_max = sys_max_check(offset_max + max(sched[0][0], sched[0][1]))
        p_range = p_max - p_min
        step_size = p_range / (n - 1)
        half_step = round(step_size / 2.0)

        if mode == 'fixed':
            order_price = p_min + int(i * step_size)
        elif mode == 'jittered':
            order_price = p_min + int(i * step_size) + random.randint(-half_step, half_step)
        elif mode == 'random':
            if len(sched) > 1:
                # more than one schedule: choose one equiprobably
                s = random.randint(0, len(sched) - 1)
                p_min = sys_min_check(min(sched[s][0], sched[s][1]))
                p_max = sys_max_check(max(sched[s][0], sched[s][1]))
            order_price = random.randint(p_min, p_max)
        else:
            sys.exit('FAIL: Unknown mode in schedule')
        order_price = sys_min_check(sys_max_check(order_price))
        return order_price

    def get_issue_times(n_traders, mode, interval, shuffle, fit_to_interval):

        interval = float(interval)
        if n_traders < 1:
            sys.exit('FAIL: n_traders < 1 in get_issue_times()')
        elif n_traders == 1:
            t_step = interval
        else:
            t_step = interval / (n_traders - 1)
        arr_time = 0
        issue_times = []
        for t in range(n_traders):
            if mode == 'periodic':
                arr_time = interval
            elif mode == 'drip-fixed':
                arr_time = t * t_step
            elif mode == 'drip-jitter':
                arr_time = t * t_step + t_step * random.random()
            elif mode == 'drip-poisson':
                # poisson requires a bit of extra work
                inter_arrival_time = random.expovariate(n_traders / interval)
                arr_time += inter_arrival_time
            else:
                sys.exit('FAIL: unknown time-mode in get_issue_times()')
            issue_times.append(arr_time)

        # at this point, arr_time is the last arrival time
        if fit_to_interval and ((arr_time > interval) or (arr_time < interval)):
            # generated sum of inter-arrival times longer than the interval
            # squish them back so that last arrival falls at t=interval
            for t in range(n_traders):
                issue_times[t] = interval * (issue_times[t] / arr_time)
        # optionally randomly shuffle the times
        if shuffle:
            for t in range(n_traders):
                i = (n_traders - 1) - t
                j = random.randint(0, i)
                tmp = issue_times[i]
                issue_times[i] = issue_times[j]
                issue_times[j] = tmp
        return issue_times

    def get_sched_mode(time, os):
        got_one = False
        for sched in os:
            if (sched['from'] <= time) and (time < sched['to']):
                # within the timezone for this schedule
                schedrange = sched['ranges']
                mode = sched['stepmode']
                sched_end_time = sched['to']
                got_one = True
                break  # jump out the loop -- so the first matching timezone has priority over any others
        if not got_one:
            sys.exit('Fail: time=%5.2f not within any timezone in os=%s' % (time, os))
        return schedrange, mode, sched_end_time

    n_buyers = trader_stats['n_buyers']
    n_sellers = trader_stats['n_sellers']

    shuffle_times = True

    cancellations = []

    if len(pending) < 1:
        # list of pending (to-be-issued) customer orders is empty, so generate a new one
        new_pending = []

        # demand side (buyers)
        issue_times = get_issue_times(n_buyers, os['timemode'], os['interval'], shuffle_times, True)
        order_type = 'Bid'
        (sched, mode, sched_end) = get_sched_mode(time, os['dem'])
        for t in range(n_buyers):
            issue_time = time + issue_times[t]
            t_name = 'B%02d' % t
            order_price = get_order_price(t, sched, sched_end, n_buyers, mode, issue_time)
            order = Order(t_name, order_type, order_price, 1, issue_time, coid, -3.14)
            new_pending.append(order)
            coid += 1

        # supply side (sellers)
        issue_times = get_issue_times(n_sellers, os['timemode'], os['interval'], shuffle_times, True)
        order_type = 'Ask'
        (sched, mode, sched_end) = get_sched_mode(time, os['sup'])
        for t in range(n_sellers):
            issue_time = time + issue_times[t]
            t_name = 'S%02d' % t
            order_price = get_order_price(t, sched, sched_end, n_sellers, mode, issue_time)
            order = Order(t_name, order_type, order_price, 1, issue_time, coid, -3.14)
            new_pending.append(order)
            coid += 1
    else:
        # there are pending future orders: issue any whose timestamp is in the past
        new_pending = []
        for order in pending:
            if order.time < time:
                # this order should have been issued by now
                # issue it to the trader
                t_name = order.tid
                response = traders[t_name].add_order(order, verbose)
                if verbose:
                    print('Customer order: %s %s' % (response, order))
                if response == 'LOB_Cancel':
                    cancellations.append(t_name)
                    if verbose:
                        print('Cancellations: %s' % cancellations)
                # and then don't add it to new_pending (i.e., delete it)
            else:
                # this order stays on the pending list
                new_pending.append(order)
    return [new_pending, cancellations, coid]
