#!/usr/bin/python

from __future__ import division, print_function, absolute_import, unicode_literals
import argparse
import btrfs
import hilbert
import png


try:
    xrange
except NameError:
    xrange = range


def device_size_offsets(fs):
    bytes_seen = 0
    offsets = {}
    for device in fs.devices():
        offsets[device.devid] = bytes_seen
        bytes_seen += device.total_bytes
    return bytes_seen, offsets


def finish_pixel(png_grid, pos, debug):
    used_pct = png_grid[pos.y][pos.x]
    if isinstance(used_pct, int) and used_pct == 0:
        return
    brightness = 16 + int(round(used_pct * (255 - 16)))
    png_grid[pos.y][pos.x] = brightness
    if debug is True:
        print("{0} value {1}".format(pos, brightness))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--order",
        type=int,
        default=10,
        help="Hilbert curve order (default: 10)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        help="increase debug output verbosity",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="pngfile",
        help="Output png file name",
    )
    parser.add_argument(
        "mountpoint",
        help="Btrfs filesystem mountpoint",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    order = args.order
    debug = args.verbose > 0
    path = args.mountpoint
    pngfile = args.pngfile

    fs = btrfs.FileSystem(path)
    total_size, dev_offset = device_size_offsets(fs)

    walk = hilbert.curve(order)
    pos = next(walk)
    png_grid = [[0 for x in xrange(pos.width)] for y in xrange(pos.height)]
    bytes_per_pixel = total_size / pos.num_steps
    print("order {0} total_size {1} bytes per pixel {2} pixels {3}".format(
        order, total_size, bytes_per_pixel, pos.num_steps))

    block_group_cache = {}
    for dev_extent in fs.dev_extents():
        if dev_extent.vaddr in block_group_cache:
            block_group = block_group_cache[dev_extent.vaddr]
        else:
            block_group = fs.block_group(dev_extent.vaddr)
            if block_group.flags & btrfs.BLOCK_GROUP_PROFILE_MASK != 0:
                block_group_cache[dev_extent.vaddr] = fs.block_group(dev_extent.vaddr)
        used_pct = block_group.used / block_group.length

        first_byte = dev_offset[dev_extent.devid] + dev_extent.paddr
        last_byte = first_byte + dev_extent.length
        first_pixel = int(first_byte / bytes_per_pixel)
        last_pixel = int(last_byte / bytes_per_pixel)

        if pos.linear < first_pixel:
            finish_pixel(png_grid, pos, debug)
            while pos.linear < first_pixel:
                pos = next(walk)

        if first_pixel == last_pixel:
            pct_of_pixel = dev_extent.length / bytes_per_pixel
            print("devid {0} pstart {1} pend {2} used_pct {3} type {4} in_pixel {5} {6}%".format(
                dev_extent.devid, dev_extent.paddr, dev_extent.paddr + dev_extent.length,
                int(round(used_pct * 100)),
                btrfs.utils.block_group_flags_str(block_group.flags),
                first_pixel, int(round(pct_of_pixel * 100))))
            png_grid[pos.y][pos.x] += pct_of_pixel * used_pct
        else:
            pct_of_first_pixel = \
                (bytes_per_pixel - (first_byte % bytes_per_pixel)) / bytes_per_pixel
            pct_of_last_pixel = (last_byte % bytes_per_pixel) / bytes_per_pixel
            print("devid {0} pstart {1} pend {2} used_pct {3} type {4} "
                  "first_pixel {5} {6}% last_pixel {7} {8}%".format(
                      dev_extent.devid, dev_extent.paddr, dev_extent.paddr + dev_extent.length,
                      int(round(used_pct * 100)),
                      btrfs.utils.block_group_flags_str(block_group.flags),
                      first_pixel, int(round(pct_of_first_pixel * 100)),
                      last_pixel, int(round(pct_of_last_pixel * 100))))
            png_grid[pos.y][pos.x] += pct_of_first_pixel * used_pct
            finish_pixel(png_grid, pos, debug)
            for _ in xrange(first_pixel + 1, last_pixel):
                pos = next(walk)
                png_grid[pos.y][pos.x] = used_pct
                finish_pixel(png_grid, pos, debug)
            pos = next(walk)
            png_grid[pos.y][pos.x] += pct_of_last_pixel * used_pct
    finish_pixel(png_grid, pos, debug)
    if pngfile is not None:
        png.from_array(png_grid, 'L').save(pngfile)


if __name__ == '__main__':
    main()