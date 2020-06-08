import csv

ratios = []

with open('fullinput.csv', newline = '') as csvfile:
	rse_output = open('rse-output.csv', 'w')
	reader = csv.reader(csvfile, delimiter=',')
	for row in reader:
		name = ['00', '00', '00', '00']
		for x in range(0, 4):
			if len(row[x]) == 1:
				name[x] = row[x].zfill(2)
			else:
				name[x] = row[x]
		with open('Results/'+name[0]+'-'+name[1]+'-'+name[2]+'-'+name[3]+'.csv') as testfile:
			newreader = csv.reader(testfile, delimiter=',')
			total = [0, 0, 0, 0]
			winner = [0, 0, 0, 0]
			if int(name[3]) != 0:
				first = 0
				if int(name[2]) != 0:
					second = 1
					if int(name[1]) != 0:
						third = 2
						forth = 3
					else:
						third = 3
				elif int(name[1]) != 0:
					second = 2
					third = 3
				else:
					second = 3
			elif int(name[2]) != 0:
				first = 1
				if int(name[1]) != 0:
					second = 2
					third = 3
				else:
					second = 3	
			else:
				first = 2
				second = 3
		
			for row in newreader:
				# print(row)
				if len(row) == 10:
					total[first] += float(row[4])
					total[second] += float(row[8])
					if float(row[4]) > float(row[8]):
						winner[first] += 1 
					else:
						winner[second] += 1						

				if len(row) == 14:
					total[first] += float(row[4])
					total[second] += float(row[8])
					total[third] += float(row[12])
					if max(float(row[4]), float(row[8]), float(row[12])) == float(row[4]):
						winner[first] += 1
					elif max(float(row[4]), float(row[8]), float(row[12])) == float(row[8]):
						winner[second] += 1
					else:
						winner[third] += 1

				if len(row) == 18:
					total[first] += float(row[4])
					total[second] += float(row[8])
					total[third] += float(row[12])
					total[forth] += float(row[16])
					if max(float(row[4]), float(row[8]), float(row[12]), float(row[16])) == float(row[4]):
						winner[first] += 1
					elif max(float(row[4]), float(row[8]), float(row[12]), float(row[16])) == float(row[8]):
						winner[second] += 1
					elif max(float(row[4]), float(row[8]), float(row[12]), float(row[16])) == float(row[12]):
						winner[third] += 1
					else:
						winner[forth] += 1

		

		rse_output.write('AA- Wins: %d Total: %d, GDX- Wins: %d Total: %d, ZIC- Wins: %d Total: %d, ZIP- Wins: %d, Total: %d\n' % (winner[0], total[0],  winner[1], total[1],  winner[3], total[3],  winner[2], total[2]))
		rse_output.flush()
		testfile.close()
csvfile.close()

with open('fullinput.csv', newline = '') as csvfile:
	bse_output = open('bse-output.csv', 'w')
	reader = csv.reader(csvfile, delimiter=',')
	for row in reader:
		name = ['00', '00', '00', '00']
		for x in range(0, 4):
			if len(row[x]) == 1:
				name[x] = row[x].zfill(2)
			else:
				name[x] = row[x]
		with open('Results/bse-'+name[0]+'-'+name[1]+'-'+name[2]+'-'+name[3]+'.csv') as testfile:
			newreader = csv.reader(testfile, delimiter=',')
			total = [0, 0, 0, 0]
			winner = [0, 0, 0, 0]
			if int(name[3]) != 0:
				first = 0
				if int(name[2]) != 0:
					second = 1
					if int(name[1]) != 0:
						third = 2
						forth = 3
					else:
						third = 3
				elif int(name[1]) != 0:
					second = 2
					third = 3
				else:
					second = 3
			elif int(name[2]) != 0:
				first = 1
				if int(name[1]) != 0:
					second = 2
					third = 3
				else:
					second = 3	
			else:
				first = 2
				second = 3
		
			for row in newreader:
				# print(row)
				if len(row) == 13:
					total[first] += float(row[5])
					total[second] += float(row[9])
					if float(row[5]) > float(row[9]):
						winner[first] += 1 
					else:
						winner[second] += 1						

				if len(row) == 17:
					total[first] += float(row[5])
					total[second] += float(row[9])
					total[third] += float(row[13])
					if max(float(row[5]), float(row[9]), float(row[13])) == float(row[5]):
						winner[first] += 1
					elif max(float(row[5]), float(row[9]), float(row[13])) == float(row[9]):
						winner[second] += 1
					else:
						winner[third] += 1

				if len(row) == 21:
					total[first] += float(row[5])
					total[second] += float(row[9])
					total[third] += float(row[13])
					total[forth] += float(row[17])
					if max(float(row[5]), float(row[9]), float(row[13]), float(row[17])) == float(row[5]):
						winner[first] += 1
					elif max(float(row[5]), float(row[9]), float(row[13]), float(row[17])) == float(row[9]):
						winner[second] += 1
					elif max(float(row[5]), float(row[9]), float(row[13]), float(row[17])) == float(row[13]):
						winner[third] += 1
					else:
						winner[forth] += 1

		

		bse_output.write('AA- Wins: %d Total: %d, GDX- Wins: %d Total: %d, ZIC- Wins: %d Total: %d, ZIP- Wins: %d, Total: %d\n' % (winner[0], total[0],  winner[1], total[1],  winner[3], total[3],  winner[2], total[2]))
		bse_output.flush()
		testfile.close()

bse_output.close()
rse_output.close()
csvfile.close()
