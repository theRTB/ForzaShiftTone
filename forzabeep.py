# -*- coding: utf-8 -*-
"""
Created on Sun May  7 19:35:24 2023

@author: RTB
"""

from base.gtbeep import GTBeep
from gui.gtbeep import GUIGTBeep

def main():
    global gtbeep #for debugging
    gtbeep = GUIGTBeep()

if __name__ == "__main__":
    main()