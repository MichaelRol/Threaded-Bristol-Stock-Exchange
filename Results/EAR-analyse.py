import csv

ratios = []

output = open('tear-output.csv', 'w')
for i in range(1, 20):
	name = ['00', '00']
	name[0] = str(i).zfill(2)
	name[1] = str(20-i).zfill(2)
	with open('TEAR-'+name[0]+'-'+name[1]+'.csv') as testfile:
		newreader = csv.reader(testfile, delimiter=',')
		first = 0
		second = 0
		rows = list(newreader)
		firstname = rows[0][1]
		secondname = rows[0][9]
		for row in rows:
			# print(row)
			if float(row[4]) > float(row[12]):
				first += 1
			else:
				second += 1
	output.write("%s, %d, %s, %d\n" % (firstname, first, secondname, second))
	output.flush()
	testfile.close()	
output.close()
