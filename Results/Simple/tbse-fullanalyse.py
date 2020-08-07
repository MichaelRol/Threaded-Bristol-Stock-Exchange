import csv

ratios = []

with open('fullinput.csv', newline = '') as csvfile:
	rse_output = open('tbse-analysis.csv', 'w')
	reader = csv.reader(csvfile, delimiter=',')
	for row in reader:
		name = ['00', '00', '00', '00', '00', '00']
		for x in range(0, 6):
			if len(row[x]) == 1:
				name[x] = row[x].zfill(2)
			else:
				name[x] = row[x]
		with open(name[0]+'-'+name[1]+'-'+name[2]+'-'+name[3]+'-'+name[4]+'-'+name[5]+'.csv') as testfile:
			newreader = csv.reader(testfile, delimiter=',')
			rows = list(newreader)
			firstname = rows[0][1]
			secondname = rows[0][9]
			firstavgs = [0, 0, 0, 0, 0]
			secondavgs = [0, 0, 0, 0, 0]
			num = 0
			for row in rows:
				num += 1
				firstavgs[0] += float(row[4])
				firstavgs[1] += float(row[5])
				firstavgs[2] += float(row[6])
				firstavgs[3] += float(row[7])
				firstavgs[4] += float(row[8])
				secondavgs[0] += float(row[12])
				secondavgs[1] += float(row[13])
				secondavgs[2] += float(row[14])
				secondavgs[3] += float(row[15])
				secondavgs[4] += float(row[16])
		rse_output.write("%s, %f, %f, %f, %f, %f, %s, %f, %f, %f, %f, %f\n" % (firstname, firstavgs[0]/num, firstavgs[1]/num, firstavgs[2]/num, firstavgs[3]/num, firstavgs[4]/num, \
											   secondname, secondavgs[0]/num, secondavgs[1]/num, secondavgs[2]/num, secondavgs[3]/num, secondavgs[4]/num))
		rse_output.flush()
		testfile.close()
rse_output.close()
csvfile.close()
