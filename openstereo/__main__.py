import sys

def my_excepthook(type, value, tback):
    # log the exception here

    # then call the default handler
    sys.__excepthook__(type, value, tback)

# from https://stackoverflow.com/a/38020962/1457481
sys.excepthook = my_excepthook

if __name__ == '__main__':
    from openstereo.os_base import os_main
    os_main()
