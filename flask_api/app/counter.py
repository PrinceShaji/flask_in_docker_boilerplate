from time import sleep


def counter(number):
    """ This function counts from 0 to %number and sleeps for a second in between """
    for i in range(number):
        sleep(1)
        print(f"The number is {i}")
