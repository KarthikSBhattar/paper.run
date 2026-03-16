def max_value(a, b):
    if a > b:
        return a
    else:
        return b

def main():
    winner = max_value(18, 7)
    if winner == 18:
        return winner
    else:
        return 0
