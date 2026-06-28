"""Запуск MicroNoise.

    py -3.8 main.py

или, если Python 3.8 — основной:

    python main.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from noiseclean.__main__ import main

if __name__ == "__main__":
    main()
