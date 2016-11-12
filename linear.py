#!/usr/bin/python

from __future__ import division, print_function, absolute_import, unicode_literals


class Position(object):
    def __init__(self, order):
        self.x = 0
        self.y = 0
        self.linear = 0
        self.width = 2 ** order
        self.height = 2 ** order
        self.num_steps = (2 ** order) ** 2

    def next(self):
        self.linear += 1
        if self.x < self.width - 1:
            self.x += 1
        else:
            self.x = 0
            self.y += 1

    def __str__(self):
        return "linear {0} y {1} x {2}".format(self.linear, self.y, self.x)


def notsocurvy(order):
    pos = Position(order)
    for i in range((2 ** order) ** 2):
        yield pos
        pos.next()


if __name__ == '__main__':
    import sys
    order = int(sys.argv[1])
    for pos in notsocurvy(order):
        print(pos)
