
# From original BSE code by Dave Cliff

# an Order/quote has a trader id, a type (buy/sell) price, quantity, timestamp, and unique i.d.
class Order:

	def __init__(self, tid, otype, price, qty, time, coid, toid):
		self.tid = tid      # trader i.d.
		self.otype = otype  # order type
		self.price = price  # price
		self.qty = qty      # quantity
		self.time = time    # timestamp
		self.coid = coid      # customer order i.d. (unique to each quote customer order)
		self.toid = toid      # trader order i.d. (unique to each order posted by the trader)

	def __str__(self):
		return '[%s %s P=%03d Q=%s T=%5.2f COID:%d TOID:%d]' % \
				(self.tid, self.otype, self.price, self.qty, self.time, self.coid, self.toid)

