#!/usr/bin/python

import png

debug = False

device_size = [0]
chunks = []

order = 10
width = 2 ** order
height = 2 ** order
num_pixels = width * height

pixels = [[] for x in xrange(num_pixels)]

lines = open('output').read().splitlines()
for line in lines:
    fields = line.split()
    if fields[0] == 'chunk':
        chunks.append({
            'type': int(fields[4]),
            'devid': int(fields[8]),
            'offset': int(fields[10]),
            'length': int(fields[12]),
            'used': int(fields[14]),
        })
    elif fields[0] == 'dev':
        devid = int(fields[3])
        while devid > len(device_size):
            device_size.append(0)
        device_size.append(int(fields[6]))

device_offset = []
for i in range(len(device_size)):
    device_offset.append(sum(device_size[:i]))

bytes_per_pixel = float(sum(device_size)) / num_pixels
print("bytes per pixel: %s" % bytes_per_pixel)

for chunk in chunks:
    first_byte = device_offset[chunk['devid']] + chunk['offset']
    last_byte = first_byte + chunk['length'] - 1
    used_pct = float(chunk['used']) / float(chunk['length'])

    first_pixel = int(first_byte / bytes_per_pixel)
    last_pixel = int(last_byte / bytes_per_pixel)

    if debug:
        print("chunk %s first_byte %s last_byte %s first_pixel %s last_pixel %s" %
              (chunk, first_byte, last_byte, first_pixel, last_pixel))

    if first_pixel == last_pixel:
        pct_of_pixel = chunk['length'] / bytes_per_pixel
        pixels[first_pixel].append((pct_of_pixel, used_pct))
    else:
        pct_of_first_pixel = (bytes_per_pixel - (first_byte % bytes_per_pixel)) / bytes_per_pixel
        pixels[first_pixel].append((pct_of_first_pixel, used_pct))

        for intermediate_pixel in xrange(first_pixel + 1, last_pixel):
            pixels[intermediate_pixel].append((1, used_pct))

        pct_of_last_pixel = (last_byte % bytes_per_pixel) / bytes_per_pixel
        pixels[last_pixel].append((pct_of_last_pixel, used_pct))


def left(pos):
    pos[1] -= 1
    return pos


def right(pos):
    pos[1] += 1
    return pos


def up(pos):
    pos[0] -= 1
    return pos


def down(pos):
    pos[0] += 1
    return pos


instructions = {
    up: [right, up, up, right, up, down, left],
    left: [down, left, left, down, left, right, up],
    right: [up, right, right, up, right, left, down],
    down: [left, down, down, left, down, up, right],
}


def hilbert(order, direction=up, pos=None):
    if pos is None:
        pos = [(2 ** order) - 1, 0]
        yield pos
    if order == 0:
        return

    steps = instructions[direction]
    for pos in hilbert(order - 1, steps[0], pos):
        yield pos
    yield steps[1](pos)
    for pos in hilbert(order - 1, steps[2], pos):
        yield pos
    yield steps[3](pos)
    for pos in hilbert(order - 1, steps[4], pos):
        yield pos
    yield steps[5](pos)
    for pos in hilbert(order - 1, steps[6], pos):
        yield pos


png_grid = [[0 for x in xrange(width)] for y in xrange(height)]
i = 0
for pos in hilbert(order):
    gradient = 0
    if isinstance(pixels[i], list):
        if debug:
            print pixels[i]
        if len(pixels[i]) > 0:
            gradient = 0
            for pct, used in pixels[i]:
                gradient = gradient + (255 * pct * used)
            gradient = int(gradient)
    else:
        gradient = int(255 * pixels[i])
    if debug:
        print i, gradient, pixels[i]
    if gradient > 255:
        raise Exception
    png_grid[pos[0]][pos[1]] = int(gradient)
    i = i + 1

png.from_array(png_grid, 'L').save("heatmap.png")
