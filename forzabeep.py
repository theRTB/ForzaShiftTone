# -*- coding: utf-8 -*-
"""
Created on Sun May  7 19:35:24 2023

@author: RTB
"""

from base.main import ForzaBeep
from gui.main import GUIForzaBeep

def main():
    global forzabeep #for debugging
    forzabeep = GUIForzaBeep()

if __name__ == "__main__":
    main()