#!/usr/bin/python3

# Run this to create pictures to create animated gifs for the first five
# hilbert order curves and linear and snake pictures as a bonus
#
# In the end, I only used one of them in the documentation (hilbert 5)

import heatmap
import os

size = 8
white = b'\xff'


def dump_grid(filename, grid, scale, width, height):
    rows = ((pix for pix in row for _ in range(scale))
            for row in grid for _ in range(scale))
    heatmap._write_png(filename, width * scale, height * scale, rows, color_type=0)


for curve_name in ('hilbert', 'snake', 'linear'):
    for order in range(1, 6):
        width = height = 2 ** order
        total_bytes = width * height
        grid = [[b'\x00'
                 for x in range(width)]
                for y in range(height)]

        scale = 2 ** (size - order)
        curve = heatmap.curves[curve_name](order)
        png_dir = 'png/{}/{:0>2}/{:0>2}'.format(curve_name, order, size)
        try:
            os.makedirs(png_dir)
        except:
            pass
        dump_grid('{}/{:0>6}.png'.format(png_dir, 0), grid, scale, width, height)
        delay = max(1, int(100/(order*order)))
        print('convert -loop 0 -delay {} -alpha on -coalesce -deconstruct {}/*.png '
              '{}-order-{:0>2}-size-{:0>2}.gif'.format(
                 delay, png_dir, curve_name, order, size))
        for frame in range(1, total_bytes+1):
            y, x, _ = next(curve)
            grid[y][x] = white
            dump_grid('{}/{:0>6}.png'.format(png_dir, frame), grid, scale, width, height)
