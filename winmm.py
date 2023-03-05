from ctypes import *
from ctypes.wintypes import UINT
from ctypes.wintypes import DWORD

def begin(value):
    windll.winmm.timeBeginPeriod(UINT(value))
    
def end(value):
    windll.winmm.timeEndPeriod(UINT(value))