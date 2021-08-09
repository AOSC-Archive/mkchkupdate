import threading
import queue
import time

q = queue.Queue()

def test1():
    while True:
        data = q.get()
        if data is None:
            return
        print(data)

def test2():
    for i in range(20):
        time.sleep(1)
        q.put(i)
    q.put(None)
    print("b")

if __name__ == "__main__":
    t = threading.Thread(target=test2)
    t.start()
    test1()
    t.join()