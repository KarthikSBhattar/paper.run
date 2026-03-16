flag = True and not False

if flag or False:
    print(1)
else:
    print(0)

def choose(a, b):
    if a and not b:
        return 1
    else:
        return 0

print(choose(True, False))
