#!/usr/bin/python

from __future__ import division, print_function, absolute_import, unicode_literals
import argparse
import btrfs
import hilbert
import png
import os
import sys


try:
    xrange
except NameError:
    xrange = range


def device_size_offsets(devices):
    bytes_seen = 0
    offsets = {}
    for device in devices:
        offsets[device.devid] = bytes_seen
        bytes_seen += device.total_bytes
    return bytes_seen, offsets


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--order",
        type=int,
        help="Hilbert curve order (default: automatically chosen)",
    )
    parser.add_argument(
        "--size",
        type=int,
        help="Image size (default: 10). Height/width is 2^size",
    )
    parser.add_argument(
        "--blockgroup",
        type=int,
        help="Instead of a filesystem overview, show extents in a block group",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        help="increase debug output verbosity (-v, -vv, -vvv, etc)",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="pngfile",
        help="Output png file name or directory (default: filename automatically chosen)",
    )
    parser.add_argument(
        "mountpoint",
        help="Btrfs filesystem mountpoint",
    )
    return parser.parse_args()


class Grid(object):
    def __init__(self, order, total_bytes, verbose):
        self.verbose = verbose
        self.curve = hilbert.curve(order)
        self._dirty = False
        self._next_pixel()
        self.height = self.pos.height
        self.width = self.pos.width
        self.total_bytes = total_bytes
        self.bytes_per_pixel = total_bytes / self.pos.num_steps
        self._grid = [[0 for x in xrange(self.width)] for y in xrange(self.height)]
        self._finished = False

        print("grid height {0} width {1} total_bytes {2} bytes_per_pixel {3} pixels {4}".format(
            self.height, self.width, total_bytes, self.bytes_per_pixel, self.pos.num_steps))

    def grid(self, height=None, width=None):
        if self._finished is False:
            self._finish_pixel()
            self._finished = True
        if (height is not None and width is not None) \
                and (height != self.height or width != self.width):
            height = int(height)
            width = int(width)
            hscale = height / self.height
            wscale = width / self.width
            return [[self._grid[int(y//hscale)][int(x//wscale)]
                     for x in xrange(width)]
                    for y in xrange(height)]
        return self._grid

    def _next_pixel(self):
        if self._dirty is True:
            self._finish_pixel()
        self.pos = next(self.curve)
        self._dirty = False

    def _add_to_pixel(self, used_pct):
        self._grid[self.pos.y][self.pos.x] += used_pct
        self._dirty = True

    def _brightness(self, used_pct):
        return 16 + int(round(used_pct * (255 - 16)))

    def _set_pixel_brightness(self, brightness):
        self._grid[self.pos.y][self.pos.x] = brightness

    def _finish_pixel(self):
        if self._dirty is False:
            return
        used_pct = self._grid[self.pos.y][self.pos.x]
        brightness = self._brightness(used_pct)
        self._grid[self.pos.y][self.pos.x] = brightness
        if self.verbose >= 3:
            print("        pixel {0} brightness {1}".format(self.pos, brightness))

    def fill(self, first_byte, length, used_pct):
        if self._finished is True:
            raise Exception("Cannot change grid any more after retrieving the result once!")
        first_pixel = int(first_byte / self.bytes_per_pixel)
        last_pixel = int((first_byte + length - 1) / self.bytes_per_pixel)

        while self.pos.linear < first_pixel:
            self._next_pixel()

        if first_pixel == last_pixel:
            pct_of_pixel = length / self.bytes_per_pixel
            if self.verbose >= 2:
                print("    in_pixel {0} {1:.2f}%".format(first_pixel, pct_of_pixel * 100))
            self._add_to_pixel(pct_of_pixel * used_pct)
        else:
            pct_of_first_pixel = \
                (self.bytes_per_pixel - (first_byte % self.bytes_per_pixel)) / self.bytes_per_pixel
            pct_of_last_pixel = \
                ((first_byte + length) % self.bytes_per_pixel) / self.bytes_per_pixel
            if pct_of_last_pixel == 0:
                pct_of_last_pixel = 1
            if self.verbose >= 2:
                print("    first_pixel {0} {1:.2f}% last_pixel {2} {3:.2f}%".format(
                    first_pixel, pct_of_first_pixel * 100, last_pixel, pct_of_last_pixel * 100))
            # add our part of the first pixel, may be shared with previous fill
            self._add_to_pixel(pct_of_first_pixel * used_pct)
            # all intermediate pixels are ours, set brightness directly
            if self.pos.linear < last_pixel - 1:
                brightness = self._brightness(used_pct)
                if self.verbose >= 3:
                    print("        pixel range linear {0} to {1} brightness {2}".format(
                        self.pos.linear, last_pixel - 1, brightness))
                while self.pos.linear < last_pixel - 1:
                    self._next_pixel()
                    self._set_pixel_brightness(brightness)
            self._next_pixel()
            # add our part of the last pixel, may be shared with next fill
            self._add_to_pixel(pct_of_last_pixel * used_pct)


def walk_dev_extents(fs, total_bytes, dev_offset, grid, verbose):
    block_group_cache = {}
    for dev_extent in fs.dev_extents():
        if dev_extent.vaddr in block_group_cache:
            block_group = block_group_cache[dev_extent.vaddr]
        else:
            try:
                block_group = fs.block_group(dev_extent.vaddr)
            except IndexError:
                continue
            if block_group.flags & btrfs.BLOCK_GROUP_PROFILE_MASK != 0:
                block_group_cache[dev_extent.vaddr] = block_group
        used_pct = block_group.used / block_group.length
        if verbose >= 1:
            print("dev_extent devid {0} paddr {1} length {2} pend {3} type {4} "
                  "used_pct {5:.2f}".format(dev_extent.devid, dev_extent.paddr, dev_extent.length,
                                            dev_extent.paddr + dev_extent.length - 1,
                                            btrfs.utils.block_group_flags_str(block_group.flags),
                                            used_pct * 100))
        first_byte = dev_offset[dev_extent.devid] + dev_extent.paddr
        grid.fill(first_byte, dev_extent.length, used_pct)


def walk_extents(fs, block_group, grid, verbose):
    nodesize = fs.fs_info().nodesize
    tree = btrfs.ctree.EXTENT_TREE_OBJECTID
    min_key = btrfs.ctree.Key(block_group.vaddr, 0, 0)
    max_key = btrfs.ctree.Key(block_group.vaddr + block_group.length, 0, 0) + -1
    for header, _ in btrfs.ioctl.search(fs.fd, tree, min_key, max_key):
        if header.type == btrfs.ctree.EXTENT_ITEM_KEY:
            length = header.offset
        elif header.type == btrfs.ctree.METADATA_ITEM_KEY:
            length = nodesize
        else:
            continue
        first_byte = header.objectid - block_group.vaddr
        if verbose >= 1:
            print("extent vaddr {0} first_byte {1} type {2} length {3}".format(
                header.objectid, first_byte, btrfs.ctree.key_type_str(header.type), length))
        grid.fill(first_byte, length, 1)


def main():
    args = parse_args()

    path = args.mountpoint
    order = args.order
    bg_vaddr = args.blockgroup
    scope = 'filesystem' if bg_vaddr is None else 'blockgroup'
    pngfile = args.pngfile
    if pngfile is not None and os.path.isdir(pngfile):
        pngdir = pngfile
        pngfile = None
    else:
        pngdir = None

    fs = btrfs.FileSystem(path)
    fs_info = fs.fs_info()
    print(fs_info)
    if scope == 'filesystem':
        total_bytes, dev_offset = device_size_offsets(fs.devices())
        if order is None:
            import math
            order = min(10, int(math.ceil(math.log(math.sqrt(total_bytes/(32*1048576)), 2))))
        if pngfile is None:
            import time
            pngfile = "fsid_{0}_at_{1}.png".format(fs.fsid, int(time.time()))
    elif scope == 'blockgroup':
        try:
            block_group = fs.block_group(bg_vaddr)
        except IndexError:
            print("Error: no block group at vaddr {0}!".format(bg_vaddr), file=sys.stderr)
            sys.exit(1)
        total_bytes = block_group.length
        if order is None:
            import math
            order = int(math.ceil(math.log(math.sqrt(block_group.length/fs_info.sectorsize), 2)))
        if pngfile is None:
            import time
            pngfile = "fsid_{0}_blockgroup_{1}_at_{2}.png".format(
                fs.fsid, block_group.vaddr, int(time.time()))
    else:
        raise Exception("Scope {0} not implemented!".format(scope))

    if pngdir is not None:
        pngfile = os.path.join(pngdir, pngfile)

    size = args.size
    if size is None:
        size = 10
    elif size < order:
        if args.order is None:
            order = size
        else:
            print("Error: size {0} needs to be at least as bit as order {1}".format(size, order),
                  file=sys.stderr)
            sys.exit(1)

    verbose = args.verbose if args.verbose is not None else 0

    print("scope {0} order {1} size {2} pngfile {3}".format(scope, order, size, pngfile))
    grid = Grid(order, total_bytes, verbose)
    if scope == 'filesystem':
        walk_dev_extents(fs, total_bytes, dev_offset, grid, verbose)
    elif scope == 'blockgroup':
        print(block_group)
        walk_extents(fs, block_group, grid, verbose)

    if size > order:
        scale = 2 ** (size - order)
        png_grid = grid.grid(int(grid.height*scale), int(grid.width*scale))
    else:
        png_grid = grid.grid()
    png.from_array(png_grid, 'L').save(pngfile)


if __name__ == '__main__':
    main()
