import os
import sys

if sys.platform in ['linux', 'darwin']:
    if os.geteuid() != 0:
        os.system("ulimit -n 10240\nsudo python app.py\n")
else:
    os.system("python app.py\n")
