#!/usr/bin/python

from __future__ import division, print_function, absolute_import, unicode_literals

left = lambda pos: pos.left()
right = lambda pos: pos.right()
up = lambda pos: pos.up()
down = lambda pos: pos.down()

instructions = {
    up: [right, up, up, right, up, down, left],
    left: [down, left, left, down, left, right, up],
    right: [up, right, right, up, right, left, down],
    down: [left, down, down, left, down, up, right],
}


class Position(object):
    def __init__(self, order):
        self.x = 0
        self.y = (2 ** order) - 1
        self.linear = 0
        self.width = 2 ** order
        self.height = 2 ** order
        self.num_steps = (2 ** order) ** 2

    def left(self):
        self.linear += 1
        self.x -= 1
        return self

    def right(self):
        self.linear += 1
        self.x += 1
        return self

    def up(self):
        self.linear += 1
        self.y -= 1
        return self

    def down(self):
        self.linear += 1
        self.y += 1
        return self

    def __str__(self):
        return "linear {0} y {1} x {2}".format(self.linear, self.y, self.x)


def curve(order, direction=up, pos=None):
    if pos is None:
        pos = Position(order)
        yield pos
    if order == 0:
        return

    steps = instructions[direction]
    for pos in curve(order - 1, steps[0], pos):
        yield pos
    yield steps[1](pos)
    for pos in curve(order - 1, steps[2], pos):
        yield pos
    yield steps[3](pos)
    for pos in curve(order - 1, steps[4], pos):
        yield pos
    yield steps[5](pos)
    for pos in curve(order - 1, steps[6], pos):
        yield pos


if __name__ == '__main__':
    import sys
    order = int(sys.argv[1])
    for pos in curve(order):
        print(pos)
