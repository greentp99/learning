print('Hello')
salutation = 'Hello'
name = 'Ralph'
print(salutation)
print(name)



def fib(n):    # write Fibonacci series less than n
    """Print a Fibonacci series less than n."""
    a, b = 0, 1
    while a < n:
        print(a, end=' ')
        a, b = b, a+b
    print()

fib(20000)


def fullname(n):
    l = 'Muro' 
    print(n, l)

fullname('Ralph')