import itertools
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from mpl_toolkits.mplot3d import Axes3D

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

min = 50
max = 250
p0 = 150
max_traders = 20

traders = []
ratio = []
diff = []
for n_trad in range(3, max_traders):
	limitprices = []

	rangesize = max - min
	step = rangesize/ (n_trad - 1)
	for i in range(0, n_trad):
		limitprices.append(min + (i * step))

	for i in range(1, n_trad):
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

			

		traders.append(n_trad)
		ratio.append(round(i/n_trad, 2))
		diff.append((winners[0]-winners[1])/(winners[0]+winners[1]))


x = traders
y = ratio
z = diff

triang = mtri.Triangulation(x, y)

fig = plt.figure()
ax = fig.add_subplot(1,1,1, projection='3d')

ax.plot_trisurf(triang, z, cmap='jet')
ax.scatter(x,y,z, marker='.', s=10, c="black", alpha=0.5)
ax.view_init(elev=60, azim=-45)

ax.set_xlabel('X')
ax.set_ylabel('Y')
ax.set_zlabel('Z')
plt.show()