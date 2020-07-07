import itertools

# print(list(itertools.combinations(limitprices, 2)))

def assign_prices(limitprices, num_a):

	values = []
	if num_a == 1:
		for pricea in limitprices:
			b = limitprices.copy()
			a = [pricea]
			b.remove(pricea)
			values.append([a, b])
	else:
		for a in list(itertools.combinations(limitprices, num_a)):
			b = limitprices.copy()
			for element in a:
				b.remove(element)
			
			values.append([a, b])

	return values

min = 10
max = 60
p0 = 35
traders = 20

ear = []

limitprices = []

# winners = [0, 0]
rangesize = max - min
step = rangesize/ (traders - 1)
for i in range(0, traders):
	limitprices.append(min + (i * step))

for i in range(1, traders):
	assignments = assign_prices(limitprices, i)
	winners = [0, 0]
	for assignment in assignments:
		num_a = len(assignment[0])
		num_b = len(assignment[1])

		total_a = 0
		total_b = 0

		for price in assignment[0]:
			profit = price - p0
			if profit > 0:
				total_a += profit

		for price in assignment[1]:
			profit = price - p0
			if profit > 0:
				total_b += profit

		appt_a = total_a / num_a
		appt_b = total_b / num_b
		if appt_a > appt_b:
			winners[0] += 1
		elif appt_b > appt_a:
			winners[1] += 1

	ear.append(winners)

for e in ear:
	print(e[0], e[1])
# print(ear)

