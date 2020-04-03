# importing the multiprocessing module 
import threading 
import time 
import queue
import random

def Exchange(lob, q):
	while(True):
		data = q.get()
		if data < 5:
			lob[0] += 1
		else:
			lob[1] += 1
		

def TraderA(lob, q): 
	
	while(True):
		time.sleep(2)
		q.put(2)
		print("A:" + str(lob))


def TraderB(lob, q): 

	while(True):
		time.sleep(1)
		q.put(7)
		print("B:" + str(lob))


def TraderC(lob, q): 

	while(True):
		time.sleep(5)
		q.put(random.randint(0, 10))
		print("C:" + str(lob))


if __name__ == "__main__": 

	lob = [0, 0]
	q = queue.Queue()
	# creating processes 
	exchange = threading.Thread(target=Exchange, args=(lob, q))
	t1 = threading.Thread(target=TraderA, args=(lob, q))
	t2 = threading.Thread(target=TraderB, args=(lob, q))
	t3 = threading.Thread(target=TraderC, args=(lob, q))


	# starting processes 
	exchange.start()
	t1.start() 
	t2.start() 
	t3.start() 


	# # wait until processes are finished 
	# exchange.join()
	# t1.join() 
	# t2.join() 
