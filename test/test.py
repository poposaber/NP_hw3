import threading, time
def func():
    x = 0
    while x < 10:
        print("x =", x)
        x += 1
        time.sleep(1)
# t = threading.Thread(target=func, daemon=True)
# t.start()

a = {"1": 34, "2": 43}
x = a["3"]
print(x)

        