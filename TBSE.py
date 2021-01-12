# -*- coding: utf-8 -*-
#
# TBSE: The Threaded Bristol Stock Exchange
#
# Version 1.0; Augusts 1st, 2020. 
#
# ------------------------
# Copyright (c) 2020, Michael Rollins
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
# TBSE is a very simple simulation of automated execution traders
# operating on a very simple model of a limit order book (LOB) exchange
# extended from Dave Cliff's Bristol Stock Exchange (BSE). TBSE uses
# Python multi-threading to allow multiple traders to operate simultaneously
# which means that the execution time of trading algorithms can affect
# their performance.
#
# major simplifications in this version:
#       (a) only one financial instrument being traded
#       (b) traders can only trade contracts of size 1 (will add variable quantities later)
#       (c) each trader can have max of one order per single orderbook.
#       (d) traders can replace/overwrite earlier orders, and/or can cancel
#
# NB this code has been written to be readable/intelligible, not efficient!

import csv
import math
import queue
import random
import sys
import threading
import time
import datetime

from TBSE_customer_orders import customer_orders
from TBSE_exchange import Exchange
from TBSE_trader_agents import (Trader_AA, Trader_GDX, Trader_Giveaway,
								Trader_Shaver, Trader_Sniper, Trader_ZIC,
								Trader_ZIP)

# trade_stats()
# dump CSV statistics on exchange data and trader population to file for later analysis
# this makes no assumptions about the number of types of traders, or
# the number of traders of any one type -- allows either/both to change
# between successive calls, but that does make it inefficient as it has to
# re-analyse the entire set of traders on each call

# Adapted from original BSE code
def trade_stats(expid, traders, dumpfile, time, lob):
	trader_types = {}
	for t in traders:
		ttype = traders[t].ttype
		if ttype in trader_types.keys():
			t_balance = trader_types[ttype]['balance_sum'] + traders[t].balance
			t_trades = trader_types[ttype]['trades_sum'] + traders[t].n_trades
			t_time1 = trader_types[ttype]['time1'] + traders[t].times[0] / traders[t].times[2]
			t_time2 = trader_types[ttype]['time2'] + traders[t].times[1] / traders[t].times[3]
			n = trader_types[ttype]['n'] + 1
		else:
			t_balance = traders[t].balance
			t_time1 = traders[t].times[0] / traders[t].times[2]
			t_time2 = traders[t].times[1] / traders[t].times[3]
			n = 1 
			t_trades = traders[t].n_trades
		trader_types[ttype] = {'n':n, 'balance_sum':t_balance, 'trades_sum':t_trades, 'time1':t_time1, 'time2':t_time2}

	# dumpfile.write('%s, %06d, ' % (expid, time))
	dumpfile.write('%s, ' % (expid))
	for ttype in sorted(list(trader_types.keys())):
		n = trader_types[ttype]['n']
		s = trader_types[ttype]['balance_sum']
		t = trader_types[ttype]['trades_sum']
		time1 = trader_types[ttype]['time1']
		time2 = trader_types[ttype]['time2']
		dumpfile.write('%s, %d, %d, %f, %f, %f, %f, ' % (ttype, s, n, s / float(n), t / float(n),  time1 / float(n), time2 / float(n)))

	dumpfile.write('\n')



# create a bunch of traders from traders_spec
# returns tuple (n_buyers, n_sellers)
# optionally shuffles the pack of buyers and the pack of sellers
# From original BSE code
def populate_market(traders_spec, traders, shuffle, verbose):

	def trader_type(robottype, name):
		if robottype == 'GVWY':
			return Trader_Giveaway('GVWY', name, 0.00, 0)
		elif robottype == 'ZIC':
			return Trader_ZIC('ZIC', name, 0.00, 0)
		elif robottype == 'SHVR':
			return Trader_Shaver('SHVR', name, 0.00, 0)
		elif robottype == 'SNPR':
			return Trader_Sniper('SNPR', name, 0.00, 0)
		elif robottype == 'ZIP':
			return Trader_ZIP('ZIP', name, 0.00, 0)
		elif robottype == 'AA':
			return Trader_AA('AA', name, 0.00, 0)
		elif robottype == 'GDX':
			return Trader_GDX('GDX', name, 0.00, 0)
		else:
			sys.exit('FATAL: don\'t know robot type %s\n' % robottype)


	def shuffle_traders(ttype_char, n, traders):
		for swap in range(n):
			t1 = (n - 1) - swap
			t2 = random.randint(0, t1)
			t1name = '%c%02d' % (ttype_char, t1)
			t2name = '%c%02d' % (ttype_char, t2)
			traders[t1name].tid = t2name
			traders[t2name].tid = t1name
			temp = traders[t1name]
			traders[t1name] = traders[t2name]
			traders[t2name] = temp


	n_buyers = 0
	for bs in traders_spec['buyers']:
		ttype = bs[0]
		for _ in range(bs[1]):
			tname = 'B%02d' % n_buyers  # buyer i.d. string
			traders[tname] = trader_type(ttype, tname)
			n_buyers = n_buyers + 1

	if n_buyers < 1:
		sys.exit('FATAL: no buyers specified\n')

	if shuffle: shuffle_traders('B', n_buyers, traders)


	n_sellers = 0
	for ss in traders_spec['sellers']:
		ttype = ss[0]
		for _ in range(ss[1]):
			tname = 'S%02d' % n_sellers  # buyer i.d. string
			traders[tname] = trader_type(ttype, tname)
			n_sellers = n_sellers + 1

	if n_sellers < 1:
		sys.exit('FATAL: no sellers specified\n')

	if shuffle: shuffle_traders('S', n_sellers, traders)

	if verbose :
		for t in range(n_buyers):
			bname = 'B%02d' % t
			print(traders[bname])
		for t in range(n_sellers):
			bname = 'S%02d' % t
			print(traders[bname])


	return {'n_buyers':n_buyers, 'n_sellers':n_sellers}

def run_exchange(exchange, order_q, trader_qs, kill_q, start_event, start_time, sess_length, virtual_end, process_verbose, lob_verbose):

	completed_coid = {}
	start_event.wait()
	while start_event.isSet():

		virtual_time = (time.time() - start_time) * (virtual_end / sess_length)
		
		while kill_q.empty() is False:
			exchange.del_order(virtual_time, kill_q.get(), False)
		
		order = order_q.get()
		if order.coid in completed_coid:	
			if completed_coid[order.coid] == True:
				continue
		else:
			completed_coid[order.coid] = False
			
		(trade, lob) = exchange.process_order2(virtual_time, order, process_verbose)
		
		if trade is not None:
			completed_coid[order.coid] = True
			completed_coid[trade['counter']] = True
			for q in trader_qs:
				q.put([trade, order, lob])
	return 0
 
def run_trader(trader, exchange, order_q, trader_q, start_event, start_time, sess_length, virtual_end, respond_verbose, bookkeep_verbose):
	
	start_event.wait()
	
	while start_event.isSet():
		time.sleep(0.01)
		virtual_time = (time.time() - start_time) * (virtual_end / sess_length)
		time_left =  (virtual_end - virtual_time) / virtual_end
		trade = None
		order = None
		while trader_q.empty() is False:
			[trade, order, lob] = trader_q.get(block = False)
			if trade['party1'] == trader.tid: trader.bookkeep(trade, order, bookkeep_verbose, virtual_time)
			if trade['party2'] == trader.tid: trader.bookkeep(trade, order, bookkeep_verbose, virtual_time)
			time1 = time.time()
			trader.respond(virtual_time, lob, trade, respond_verbose)
			time2 = time.time()
			trader.times[1] += time2 - time1
			trader.times[3] += 1

		lob = exchange.publish_lob(virtual_time, False)
		time1 = time.time()
		trader.respond(virtual_time, lob, trade, respond_verbose)
		time2 = time.time()
		order = trader.getorder(virtual_time, time_left, lob)
		time3 = time.time()
		trader.times[1] += time2 - time1
		trader.times[3] += 1
		if order is not None:
			# print(order)
			if order.otype == 'Ask' and order.price < trader.orders[order.coid].price: sys.exit('Bad ask')
			if order.otype == 'Bid' and order.price > trader.orders[order.coid].price: sys.exit('Bad bid')
			trader.n_quotes = 1
			order_q.put(order)
			trader.times[0] += time3 - time2
			trader.times[2] += 1
		   
	return 0

# one session in the market
def market_session(sess_id, sess_length, virtual_end, trader_spec, order_schedule, dumpfile, dump_each_trade, start_event, verbose):
	
	# initialise the exchange
	exchange = Exchange()
	order_q = queue.Queue()
	kill_q = queue.Queue()

	start_time = time.time()
	

	orders_verbose = False
	lob_verbose = False
	process_verbose = False
	respond_verbose = False
	bookkeep_verbose = False
	# create a bunch of traders
	traders = {}
	trader_threads = []
	trader_qs = []
	trader_stats = populate_market(trader_spec, traders, True, verbose)
	
	# create threads and queues for traders
	for i in range(0, len(traders)):
		trader_qs.append(queue.Queue())
		tid = list(traders.keys())[i]
		trader_threads.append(threading.Thread(target=run_trader, args=(traders[tid], exchange, order_q, trader_qs[i], start_event, start_time, sess_length, virtual_end, respond_verbose, bookkeep_verbose))) 
	
	ex_thread = threading.Thread(target=run_exchange, args=(exchange, order_q, trader_qs, kill_q, start_event, start_time, sess_length, virtual_end, process_verbose, lob_verbose))
 
	# start exchange thread
	ex_thread.start()

	# start trader threads
	for thread in trader_threads:
		thread.start()

	start_event.set()

	last_update = -1.0

	pending_cust_orders = []

	if verbose: print('\n%s;  ' % (sess_id))

	cuid = 0 # Customer order id

	while time.time() < (start_time + sess_length):
		virtual_time = (time.time() - start_time) * (virtual_end / sess_length)
		# distribute customer orders
		[pending_cust_orders, kills, cuid] = customer_orders(virtual_time, cuid, last_update, traders, trader_stats,
											order_schedule, pending_cust_orders, orders_verbose)
		# if any newly-issued customer orders mean quotes on the LOB need to be cancelled, kill them
		if len(kills) > 0 :
			if verbose : print('Kills: %s' % (kills))
			for kill in kills :
				if verbose : print('lastquote=%s' % traders[kill].lastquote)
				if traders[kill].lastquote != None :
					kill_q.put(traders[kill].lastquote)
					if verbose : print('Killing order %s' % (str(traders[kill].lastquote)))
		time.sleep(0.01)

	# print("QUEUE: " + str(order_q.qsize()))
	start_event.clear()
	len_threads = len(threading.enumerate())

	# close exchange thread
	ex_thread.join()

	# close trader threads
	for thread in trader_threads:
		thread.join()


	# end of an experiment -- dump the tape
	exchange.tape_dump('transactions.csv', 'a', 'keep')


	# write trade_stats for this experiment NB end-of-session summary only
	if len_threads == len(traders) + 2:
		trade_stats(sess_id, traders, tdump, virtual_end, exchange.publish_lob(virtual_end, lob_verbose))
	return len_threads

#############################

# # Below here is where we set up and run a series of experiments


if __name__ == "__main__":

	# set up parameters for the session
	sess_length = 1 # Length of the session in seconds
	virtual_start = 0
	virtual_end = 600 # Number of virtual seconds for each session

	# schedule_offsetfn returns time-dependent offset on schedule prices
	def schedule_offsetfn(t):
		pi2 = math.pi * 2
		c = math.pi * 3000
		wavelength = t / c
		gradient = 100 * t / (c / pi2)
		amplitude = 100 * t / (c / pi2)
		offset = gradient + amplitude * math.sin(wavelength * t)
		return int(round(offset, 0))

	def real_world_schedule_offsetfn(time, params):
		end_time = float(params[0])
		offset_events = params[1]
		# this is quite inefficient: on every call it walks the event-list
		# come back and make it better
		percent_elapsed = time/end_time
		for event in offset_events:
			offset = event[1]
			if percent_elapsed < event[0]: break
		return offset

	

	### This section of code allows for the same order and trader schedules
	### to be tested n_trails times. Comment out lines 417-488 and make sure
	### that lines 349-405 are uncommented.

	range_max = random.randint(100,200)
	range_min = random.randint(1, 100)
	rangeS = (range_min, range_max,schedule_offsetfn)

	## Stepmode Options: fixed, random, jittered
	supply_schedule = [ {'from':0, 'to':virtual_end, 'ranges':[rangeS], 'stepmode':'fixed'}
						]

	range_max = random.randint(100,200)
	range_min = random.randint(1, 100)
	rangeD = (range_min, range_max,schedule_offsetfn)
	demand_schedule = [ {'from':0, 'to':virtual_end, 'ranges':[rangeD], 'stepmode':'fixed'}
						]

	## Timemode Options: periodic, drip-fixed, drip-jitter, drip-poisson
	order_sched = {'sup':supply_schedule, 'dem':demand_schedule,
					'interval':60, 'timemode':'periodic'}

	## Trader Options: GDX, AA, ZIP, ZIC, SHVR, GVWY
	buyers_spec = [('GDX', 4),('AA', 4),('ZIP', 4),('SHVR', 4)]

	sellers_spec = buyers_spec
	traders_spec = {'sellers':sellers_spec, 'buyers':buyers_spec}

	n_trials = 50
	tdump=open('avg_balance.csv','w')

	trader_count = 0
	for ttype in buyers_spec:
		trader_count += ttype[1]
	for ttype in sellers_spec:
		trader_count += ttype[1]

	trial = 1
	if n_trials > 1:
		dump_all = False
	else:
		dump_all = True
			
	while (trial<(n_trials+1)):
		trial_id = 'trial%07d' % trial
		start_event = threading.Event()
		try:
			num_threads = market_session(trial_id, sess_length, virtual_end, traders_spec,
							order_sched, tdump, False, start_event, False)
			
			if num_threads != trader_count + 2:
				trial = trial - 1
				start_event.clear()
				time.sleep(0.5)
		except:
			trial = trial - 1
			start_event.clear()
			time.sleep(0.5)
		tdump.flush()
		trial = trial + 1
	tdump.close()
	
	### To use this section of code run TBSE with 'python3 TBSE.py <csv>' 
	### and have a CSV file with name <csv>.csv with a list of values
	### representing the number of each trader type present in the 
	### market you wish to run. The order is:
	### 				ZIC,ZIP,GDX,AA,GVWY,SHVR
	### So an example entry would be: 5,5,0,0,5,5
	### which would be 5 ZIC traders, 5 ZIP traders, 5 Giveaway traders and
	### 5 Shaver traders. To have different buyer and seller specs modifications
	### would be needed.
	### Each line in the CSV file will produce its own output file.
	### Comment out lines 349-405 and make sure tha lines 417-488 are uncommented.


	# server = sys.argv[1]
	# ratios = []
	# with open(server+'.csv', newline = '') as csvfile:
	# 	reader = csv.reader(csvfile, delimiter=',')
	# 	for row in reader:
	# 		ratios.append(row)

	# n_trials_per_ratio = 100 
	# n_schedules_per_ratio = 10
	# trialnumber = 1
	
	# for ratio in ratios:
	# 	trdr_1_n = int(ratio[0])
	# 	trdr_2_n = int(ratio[1])
	# 	trdr_3_n = int(ratio[2])
	# 	trdr_4_n = int(ratio[3])
	# 	trdr_5_n = int(ratio[4])
	# 	trdr_6_n = int(ratio[5])

	# 	fname = '%02d-%02d-%02d-%02d-%02d-%02d.csv' % (trdr_1_n, trdr_2_n, trdr_3_n, trdr_4_n, trdr_5_n, trdr_6_n)

	# 	tdump = open(fname, 'w')
	# 	for _ in range(0, n_schedules_per_ratio):
	# 		range_max = random.randint(100,200)
	# 		range_min = random.randint(1, 100)
	# 		rangeS = (range_min, range_max,schedule_offsetfn)


	# ##		Stepmode Options: fixed, random, jittered
	# 		supply_schedule = [ {'from':0, 'to':virtual_end, 'ranges':[rangeS], 'stepmode':'fixed'}
	# 							]

	# 		# range_max = random.randint(100,200)
	# 		# range_min = random.randint(1, 100)
	# 		rangeD = (range_min, range_max,schedule_offsetfn)
	# 		demand_schedule = [ {'from':0, 'to':virtual_end, 'ranges':[rangeD], 'stepmode':'fixed'}
	# 							]

	# ## 		Timemode Options: periodic, drip-fixed, drip-jitter, drip-poisson
	# 		order_sched = {'sup':supply_schedule, 'dem':demand_schedule,
	# 						'interval':30, 'timemode':'periodic'}
		
	# ##		Do not touch unless you know what you are doing.	
	# 		buyers_spec = [('ZIC', trdr_1_n), ('ZIP', trdr_2_n),
	# 						('GDX', trdr_3_n), ('AA', trdr_4_n),
	# 						('GVWY', trdr_5_n), ('SHVR', trdr_6_n)]

	# 		sellers_spec = buyers_spec
	# 		traders_spec = {'sellers':sellers_spec, 'buyers':buyers_spec}
			
	# 		trial = 1
	# 		while trial <= n_trials_per_ratio:
	# 			trial_id = 'trial%07d' % trialnumber
	# 			start_event = threading.Event()
	# 			try:
	# 				num_threads = market_session(trial_id, sess_length, virtual_end, traders_spec,
	# 								order_sched, tdump, False, start_event, False)
					
	# 				if num_threads != (trdr_1_n + trdr_2_n + trdr_3_n + trdr_4_n + trdr_5_n + trdr_6_n) * 2 + 2:
	# 					trial = trial - 1
	# 					trialnumber = trialnumber - 1
	# 					start_event.clear()
	# 					time.sleep(0.5)
	# 			except:
	# 				trial = trial - 1
	# 				trialnumber = trialnumber - 1
	# 				start_event.clear()
	# 				time.sleep(0.5)
	# 			tdump.flush()
	# 			trial = trial + 1
	# 			trialnumber = trialnumber + 1
	# 	tdump.close()


	# sys.exit('Done Now')


	# server = sys.argv[1]
	# ratios = []
	# with open(server+'.csv', newline = '') as csvfile:
	# 	reader = csv.reader(csvfile, delimiter=',')
	# 	for row in reader:
	# 		ratios.append(row)

	# n_trials_per_ratio = 100 
	# n_schedules_per_ratio = 10
	# trialnumber = 1
	
	# for ratio in ratios:
	# 	trdr_1_n = int(ratio[0])
	# 	trdr_2_n = int(ratio[1])
	# 	trdr_3_n = int(ratio[2])
	# 	trdr_4_n = int(ratio[3])
	# 	trdr_5_n = int(ratio[4])
	# 	trdr_6_n = int(ratio[5])

	# 	fname = '%02d-%02d-%02d-%02d-%02d-%02d.csv' % (trdr_1_n, trdr_2_n, trdr_3_n, trdr_4_n, trdr_5_n, trdr_6_n)

	# 	tdump = open(fname, 'w')
	# 	for _ in range(0, n_schedules_per_ratio):
	# 		# read in a real-world-data data-file for the SDS offset function
	# 		# having this here means it's only read in once
	# 		# this is all quite skanky, just to get it up and running
	# 		# assumes data file is all for one date, sorted in time order, in correct format, etc. etc.
	# 		rwd_csv = csv.reader(open('RWD/ibm-1m-sample170831.csv', 'r'))
	# 		scale_factor = 80
	# 		# first pass: get time & price events, find out how long session is, get min & max price
	# 		minprice = None
	# 		maxprice = None
	# 		firsttimeobj = None
	# 		priceevents=[]
	# 		for line in rwd_csv:
	# 			print(line)
	# 			time_str = line[1]
	# 			if firsttimeobj == None: firsttimeobj = datetime.datetime.strptime(time_str, '%H:%M:%S')
	# 			timeobj=datetime.datetime.strptime(time_str, '%H:%M:%S')
	# 			price = float(line[2])
	# 			if minprice == None or price < minprice: minprice = price
	# 			if maxprice == None or price > maxprice: maxprice = price
	# 			timesincestart = (timeobj - firsttimeobj).total_seconds()
	# 			priceevents.append([timesincestart, price])
	# 		# second pass: normalise times to fractions of entire time-series duration
	# 		#              & normalise price range
	# 		pricerange = maxprice - minprice
	# 		endtime = float(timesincestart)
	# 		offsetfn_eventlist=[]
	# 		for event in priceevents:
	# 			# normalise price
	# 			normld_price = (event[1]-minprice)/pricerange
	# 			# clip
	# 			normld_price = min(normld_price,1.0)
	# 			normld_price = max(0.0,normld_price)
	# 			# scale & convert to integer cents
	# 			price = int(round(normld_price * scale_factor))
	# 			normld_event = [event[0]/endtime, price]
	# 			offsetfn_eventlist.append(normld_event)

	# 		range_max = random.randint(100,200)
	# 		range_min = random.randint(1, 100)
	# 		suprange = (range_min, range_max, [real_world_schedule_offsetfn, [offsetfn_eventlist]])
	# 		supply_schedule = [{'from': virtual_start, 'to': virtual_end, 'ranges': [suprange], 'stepmode': 'fixed'}
	# 						]
	# 		range_max = random.randint(100,200)
	# 		range_min = random.randint(1, 100)
	# 		demrange = (range_min, range_max, [real_world_schedule_offsetfn, [offsetfn_eventlist]])
	# 		demand_schedule = [{'from': virtual_start, 'to': virtual_end, 'ranges': [demrange], 'stepmode': 'fixed'}
	# 						]
	# 		order_sched = {'sup': supply_schedule, 'dem': demand_schedule,
	# 					'interval': 30, 'timemode': 'drip-poisson'}

	# 		##		Do not touch unless you know what you are doing.	
	# 		buyers_spec = [('ZIC', trdr_1_n), ('ZIP', trdr_2_n),
	# 						('GDX', trdr_3_n), ('AA', trdr_4_n),
	# 						('GVWY', trdr_5_n), ('SHVR', trdr_6_n)]

	# 		sellers_spec = buyers_spec
	# 		traders_spec = {'sellers':sellers_spec, 'buyers':buyers_spec}
			
	# 		trial = 1
	# 		while trial <= n_trials_per_ratio:
	# 			trial_id = 'trial%07d' % trialnumber
	# 			start_event = threading.Event()
	# 			try:
	# 				num_threads = market_session(trial_id, sess_length, virtual_end, traders_spec,
	# 								order_sched, tdump, False, start_event, False)
					
	# 				if num_threads != (trdr_1_n + trdr_2_n + trdr_3_n + trdr_4_n + trdr_5_n + trdr_6_n) * 2 + 2:
	# 					trial = trial - 1
	# 					trialnumber = trialnumber - 1
	# 					start_event.clear()
	# 					time.sleep(0.5)
	# 			except Exception as e:
	# 				print(e)
	# 				trial = trial - 1
	# 				trialnumber = trialnumber - 1
	# 				start_event.clear()
	# 				time.sleep(0.5)
	# 			tdump.flush()
	# 			trial = trial + 1
	# 			trialnumber = trialnumber + 1
	# 	tdump.close()