#!/usr/bin/python

import png

device_size = [0]
chunks = []

width = 1200
height = 800
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

for i in xrange(len(pixels)):
    if isinstance(pixels[i], list):
        if len(pixels[i]) == 0:
            pixels[i] = 0
        else:
            gradient = 0
            for pct, used in pixels[i]:
                gradient = gradient + (255 * pct * used)
            pixels[i] = int(gradient)
    else:
        pixels[i] = int(255 * pixels[i])

png_grid = []
for i in range(0, len(pixels), width):
    png_grid.append(pixels[i:i+width])

png.from_array(png_grid, 'L').save("heatmap.png")
