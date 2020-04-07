import sys
import math
import threading 
import time 
import queue
import random
from RSE_exchange import Exchange
from RSE_customer_orders import customer_orders
from RSE_trader_agents import Trader_Giveaway, Trader_Shaver, Trader_Sniper, Trader_ZIC, Trader_ZIP


# trade_stats()
# dump CSV statistics on exchange data and trader population to file for later analysis
# this makes no assumptions about the number of types of traders, or
# the number of traders of any one type -- allows either/both to change
# between successive calls, but that does make it inefficient as it has to
# re-analyse the entire set of traders on each call
def trade_stats(expid, traders, dumpfile, time, lob):
	
	trader_types = {}
	# n_traders = len(traders)
	for t in traders:
			ttype = traders[t].ttype
			if ttype in trader_types.keys():
					t_balance = trader_types[ttype]['balance_sum'] + traders[t].balance
					n = trader_types[ttype]['n'] + 1
			else:
					t_balance = traders[t].balance
					n = 1
			trader_types[ttype] = {'n':n, 'balance_sum':t_balance}


	dumpfile.write('%s, %06d, ' % (expid, time))
	for ttype in sorted(list(trader_types.keys())):
			n = trader_types[ttype]['n']
			s = trader_types[ttype]['balance_sum']
			dumpfile.write('%s, %d, %d, %f, ' % (ttype, s, n, s / float(n)))

	if lob['bids']['best'] != None :
			dumpfile.write('%d, ' % (lob['bids']['best']))
	else:
			dumpfile.write('N, ')
	if lob['asks']['best'] != None :
			dumpfile.write('%d, ' % (lob['asks']['best']))
	else:
			dumpfile.write('N, ')
	dumpfile.write('\n')





# create a bunch of traders from traders_spec
# returns tuple (n_buyers, n_sellers)
# optionally shuffles the pack of buyers and the pack of sellers
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

def run_exchange(exchange, lob, order_q, trader_qs, start_event, start_time, sess_length, virtual_end, process_verbose, lob_verbose):

	start_event.wait()
	while start_event.isSet():

		virtual_time = (time.time() - start_time) * (virtual_end / sess_length)
		lob = exchange.publish_lob(virtual_time, lob_verbose)
		# print(lob)
		order = order_q.get()
		trade = exchange.process_order2(virtual_time, order, process_verbose)

		if trade is not None:
			lob = exchange.publish_lob(virtual_time, lob_verbose)
			for q in trader_qs:
				q.put([trade, order])

	return 0
 
def run_trader(trader, lob, order_q, trader_q, start_event, start_time, sess_length, virtual_end, respond_verbose, bookkeep_verbose):
	
	start_event.wait()
	while start_event.isSet():

		virtual_time = (time.time() - start_time) * (virtual_end / sess_length)
		time_left =  (virtual_end - virtual_time) / virtual_end

		while trader_q.empty() is False:
			[trade, order] = trader_q.get(block = False)
			trader.respond(virtual_time, lob, trade, respond_verbose)
			# IF MINE THEN BOOK KEEPING
			if trade['party1'] == trader.tid: trader.bookkeep(trade, order, bookkeep_verbose, virtual_time)
			if trade['party2'] == trader.tid: trader.bookkeep(trade, order, bookkeep_verbose, virtual_time)


		order = trader.getorder(virtual_time, time_left, lob)
		print(order)

		if order is not None:
			if order.otype == 'Ask' and order.price < trader.orders[0].price: sys.exit('Bad ask')
			if order.otype == 'Bid' and order.price > trader.orders[0].price: sys.exit('Bad bid')
			trader.n_quotes = 1
			order_q.put(order)

	return 0

# one session in the market
def market_session(sess_id, sess_length, virtual_end, trader_spec, order_schedule, dumpfile, dump_each_trade, verbose):
	
	# initialise the exchange
	exchange = Exchange()
	lob = exchange.publish_lob(time.time(), verbose)
	order_q = queue.Queue()
	
	start_time = time.time()
	start_event = threading.Event()

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
		trader_threads.append(threading.Thread(target=run_trader, args=(traders[tid], lob, order_q, trader_qs[i], start_event, start_time, sess_length, virtual_end, respond_verbose, bookkeep_verbose))) 
	
	ex_thread = threading.Thread(target=run_exchange, args=(exchange, lob, order_q, trader_qs, start_event, start_time, sess_length, virtual_end, process_verbose, lob_verbose))
 
	# start exchange thread
	ex_thread.start()

	# start trader threads
	for thread in trader_threads:
		thread.start()

	start_event.set()

	last_update = -1.0

	pending_cust_orders = []

	if verbose: print('\n%s;  ' % (sess_id))

	while time.time() < (start_time + sess_length):
		virtual_time = (time.time() - start_time) * (virtual_end / sess_length)
		# distribute customer orders
		[pending_cust_orders, kills] = customer_orders(virtual_time, last_update, traders, trader_stats,
											order_schedule, pending_cust_orders, orders_verbose)

		# if any newly-issued customer orders mean quotes on the LOB need to be cancelled, kill them
		if len(kills) > 0 :
				# if verbose : print('Kills: %s' % (kills))
				for kill in kills :
						# if verbose : print('lastquote=%s' % traders[kill].lastquote)
						if traders[kill].lastquote != None :
								# if verbose : print('Killing order %s' % (str(traders[kill].lastquote)))
								exchange.del_order(virtual_time, traders[kill].lastquote, verbose)


	start_event.clear()
	# end of an experiment -- dump the tape
	exchange.tape_dump('transactions.csv', 'w', 'keep')


	# write trade_stats for this experiment NB end-of-session summary only
	trade_stats(sess_id, traders, tdump, virtual_end, exchange.publish_lob(virtual_end, lob_verbose))



#############################

# # Below here is where we set up and run a series of experiments


if __name__ == "__main__":

	# set up parameters for the session
	sess_length = 20.0 # Length of the session in seconds
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
			

	range1 = (95, 95, schedule_offsetfn)
	supply_schedule = [ {'from':0, 'to':virtual_end, 'ranges':[range1], 'stepmode':'fixed'}
						]

	range1 = (105, 105, schedule_offsetfn)
	demand_schedule = [ {'from':0, 'to':virtual_end, 'ranges':[range1], 'stepmode':'fixed'}
						]

	order_sched = {'sup':supply_schedule, 'dem':demand_schedule,
					'interval':30, 'timemode':'drip-poisson'}


	# run a sequence of trials that exhaustively varies the ratio of four trader types
	# NB this has weakness of symmetric proportions on buyers/sellers -- combinatorics of varying that are quite nasty	

	# n_trader_types = 4
	# equal_ratio_n = 4
	# n_trials_per_ratio = 50

	# n_traders = n_trader_types * equal_ratio_n

	# fname = 'balances_%03d.csv' % equal_ratio_n

	# tdump = open(fname, 'w')

	# min_n = 1

	# trialnumber = 1
	# trdr_1_n = min_n
	# while trdr_1_n <= n_traders:
	# 		trdr_2_n = min_n 
	# 		while trdr_2_n <= n_traders - trdr_1_n:
	# 				trdr_3_n = min_n
	# 				while trdr_3_n <= n_traders - (trdr_1_n + trdr_2_n):
	# 						trdr_4_n = n_traders - (trdr_1_n + trdr_2_n + trdr_3_n)
	# 						if trdr_4_n >= min_n:
	# 								buyers_spec = [('GVWY', trdr_1_n), ('SHVR', trdr_2_n),
	# 												('ZIC', trdr_3_n), ('ZIP', trdr_4_n)]
	# 								sellers_spec = buyers_spec
	# 								traders_spec = {'sellers':sellers_spec, 'buyers':buyers_spec}
	# 								# print buyers_spec
	# 								trial = 1
	# 								while trial <= n_trials_per_ratio:
	# 										trial_id = 'trial%07d' % trialnumber
	# 										market_session(trial_id, sess_length, virtual_end, traders_spec,
	# 														order_sched, tdump, False, True)
	# 										tdump.flush()
	# 										trial = trial + 1
	# 										trialnumber = trialnumber + 1
	# 						trdr_3_n += 1
	# 				trdr_2_n += 1
	# 		trdr_1_n += 1
	# tdump.close()
	
	# print(trialnumber)

	buyers_spec = [('GVWY',2),('SHVR',2),('ZIC',2),('ZIP',2)]
	sellers_spec = buyers_spec
	traders_spec = {'sellers':sellers_spec, 'buyers':buyers_spec}

	# run a sequence of trials, one session per trial

	n_trials = 10
	tdump=open('avg_balance.csv','w')
	trial = 1
	if n_trials > 1:
			dump_all = False
	else:
			dump_all = True
			
	while (trial<(n_trials+1)):
			trial_id = 'trial%04d' % trial
			market_session(trial_id, sess_length, virtual_end, traders_spec,
											order_sched, tdump, False, True)
			tdump.flush()
			trial = trial + 1
	tdump.close()

	sys.exit('Done Now')