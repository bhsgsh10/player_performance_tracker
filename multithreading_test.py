import multiprocessing
import threading
import os
import time
import sched
from datetime import datetime, timezone, timedelta
import pytz
import schedule


scheduler = sched.scheduler(time.time, time.sleep)
api_key = os.environ.get("rapid_football_api_key")

def print_time(a='default'):
    print("From print_time", time.time(), a)

'''
A number representing the delay
A priority value
The function to call
A tuple of arguments for the function
'''
def print_times():

    # get current epoch time
    # get epoch time for 5 mins later
    # the difference of the time is 5*60 secs
    # schedule an API call 5 mins from the current time
    now_utc = datetime.now(timezone.utc).strftime("%b %d %Y %H:%M:%S")
    epoch_now = int(time.mktime(time.strptime(now_utc, "%b %d %Y %H:%M:%S")))
    scheduled_timestamp = epoch_now + 20
    #print(f"Time in epoch is {time.gmtime(epoch_now)}")
    # scheduler.enterabs(scheduled_timestamp, 1, print_time, ('Alaba',), {})
    scheduler.enter(scheduled_timestamp - epoch_now, 1, print_time, ('Alaba',))

    # scheduler.enter(10, 1, print_time, ('Alaba',))
    # scheduler.enter(30, 1, print_time, ('Mandzukic',))
    scheduler.run()



def test(a,b):
    while True:
        print('Process 2 called')
        index = 0
        while index < 10:
            if a > b:
                scheduler.enter(2, 1, print_time, ())
                scheduler.run()
            index += 1
        time.sleep(15)

def spawn():
    while True:
        print('Process 1 called')
        time.sleep(10)
        

def multiply(a,b,product,que): #add a argument to function for assigning a queue
    while True:
        new_product = product * a * b

        que.put(new_product) 

# if __name__ == '__main__':
#     # queue1 = multiprocessing.Queue() #create a queue object
#     # product = 20
#     # p = multiprocessing.Process(target= multiply, args= (5,4,product,queue1)) #we're setting 3rd argument to queue1
#     # p.start()
#     # print(queue1.get()) #and we're getting return value: 20
#     # p.join()
#     # print("ok.")
#     print_times()
if __name__ == "__main__":
    # p1 = multiprocessing.Process(target=spawn)
    # p1.start()
    
    # p2 = multiprocessing.Process(target=test, args=(8,7))
    # p2.start()

    # read the rapid api key from the environment variables
    print(api_key)  
    t = datetime.now(pytz.utc)
    print(type(t.hour))
    print(t.isoweekday())
    # schedule.every().friday.at("13:59").do(print_time)
    # while 1:
    #     schedule.run_pending()
    #     time.sleep(1)

    



    
    