import llnl.util.tty as tty


def bold(msg):
    return tty.color.colorize("@*{" + msg + "}")
