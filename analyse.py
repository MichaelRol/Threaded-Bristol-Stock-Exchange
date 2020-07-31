import csv

ratios = []

with open('fullinput.csv', newline = '') as csvfile:
	rse_output = open('bse-output.csv', 'w')
	reader = csv.reader(csvfile, delimiter=',')
	for row in reader:
		name = ['00', '00', '00', '00', '00', '00']
		for x in range(0, 6):
			if len(row[x]) == 1:
				name[x] = row[x].zfill(2)
			else:
				name[x] = row[x]
		with open('bse-'+name[0]+'-'+name[1]+'-'+name[2]+'-'+name[3]+'-'+name[4]+'-'+name[5]+'.csv') as testfile:
			newreader = csv.reader(testfile, delimiter=',')
			# total = [0, 0, 0, 0, 0, 0]
			# winner = [0, 0, 0, 0, 0, 0]
			first = 0
			second = 0
			rows = list(newreader)
			firstname = rows[0][1]
			secondname = rows[0][8]
			for row in rows:
				# print(row)
				if float(row[4]) > float(row[11]):
					first += 1
				else:
					second += 1
		rse_output.write("%s, %d, %s, %d\n" % (firstname, first, secondname, second))
		rse_output.flush()
		testfile.close()
rse_output.close()
csvfile.close()
