import os
import shutil

import llnl.util.tty as tty


def bold(msg):
    return tty.color.colorize("@*{" + msg + "}")


def clean(dirpath):
    for filename in os.listdir(dirpath):
        filepath = os.path.join(dirpath, filename)
        try:
            shutil.rmtree(filepath)
        except OSError:
            os.remove(filepath)
