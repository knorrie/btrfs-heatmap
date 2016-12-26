#!/usr/bin/python

from __future__ import division, print_function, absolute_import, unicode_literals
import argparse
import btrfs
import hilbert
import os
import struct
import sys
import types
import zlib


try:
    xrange
except NameError:
    xrange = range


class HeatmapError(Exception):
    pass


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
        dest="output",
        help="Output png file name or directory (default: filename automatically chosen)",
    )
    parser.add_argument(
        "mountpoint",
        help="Btrfs filesystem mountpoint",
    )
    return parser.parse_args()


struct_color = struct.Struct('!BBB')

black = (0x00, 0x00, 0x00)
white = (0xff, 0xff, 0xff)
red = (0xff, 0x00, 0x33)
blue = (0x00, 0x66, 0xff)
blue_white = (0x99, 0xcc, 0xff)  # for mixed bg

dev_extent_colors = {
    btrfs.BLOCK_GROUP_DATA: white,
    btrfs.BLOCK_GROUP_METADATA: blue,
    btrfs.BLOCK_GROUP_SYSTEM: red,
    btrfs.BLOCK_GROUP_DATA | btrfs.BLOCK_GROUP_METADATA: blue_white,
}


class Grid(object):
    def __init__(self, order, size, total_bytes, default_granularity, verbose,
                 min_brightness=None):
        self.order, self.size = choose_order_size(order, size, total_bytes, default_granularity)
        self.verbose = verbose
        self.curve = hilbert.curve(self.order)
        self._pixel_mix = []
        self._pixel_dirty = False
        self._next_pixel()
        self.height = self.pos.height
        self.width = self.pos.width
        self.total_bytes = total_bytes
        self.bytes_per_pixel = total_bytes / self.pos.num_steps
        self._color_cache = {}
        self._add_color_cache(black)
        self._grid = [[self._color_cache[black]
                       for x in xrange(self.width)]
                      for y in xrange(self.height)]
        self._finished = False
        if min_brightness is None:
            self._min_brightness = 0.1
        else:
            if min_brightness < 0 or min_brightness > 1:
                raise ValueError("min_brightness out of range (need >= 0 and <= 1)")
            self._min_brightness = min_brightness
        print("grid order {} size {} height {} width {} total_bytes {} bytes_per_pixel {}".format(
            self.order, self.size, self.height, self.width,
            total_bytes, self.bytes_per_pixel, self.pos.num_steps))

    def _next_pixel(self):
        if self._pixel_dirty is True:
            self._finish_pixel()
        self.pos = next(self.curve)

    def _add_to_pixel_mix(self, color, used_pct, pixel_pct):
        self._pixel_mix.append((color, used_pct, pixel_pct))
        self._pixel_dirty = True

    def _pixel_mix_to_rgbytes(self):
        R_composite = sum(color[0] * pixel_pct for color, _, pixel_pct in self._pixel_mix)
        G_composite = sum(color[1] * pixel_pct for color, _, pixel_pct in self._pixel_mix)
        B_composite = sum(color[2] * pixel_pct for color, _, pixel_pct in self._pixel_mix)

        weighted_usage = sum(used_pct * pixel_pct
                             for _, used_pct, pixel_pct in self._pixel_mix)
        weighted_usage_min_bright = self._min_brightness + \
            weighted_usage * (1 - self._min_brightness)

        R = int(round(R_composite * weighted_usage_min_bright))
        G = int(round(G_composite * weighted_usage_min_bright))
        B = int(round(B_composite * weighted_usage_min_bright))

        return self._color_cache.get((R, G, B), self._add_color_cache((R, G, B)))

    def _add_color_cache(self, color):
        rgbytes = struct_color.pack(*color)
        self._color_cache[color] = rgbytes
        return rgbytes

    def _set_pixel(self, rgbytes):
        self._grid[self.pos.y][self.pos.x] = rgbytes

    def _finish_pixel(self):
        rgbytes = self._pixel_mix_to_rgbytes()
        self._set_pixel(rgbytes)
        if self.verbose >= 3:
            print("        pixel {} rgb #{}".format(
                self.pos, ''.join('{:02x}'.format(ord(byte)) for byte in rgbytes)))
        self._pixel_mix = []
        self._pixel_dirty = False

    def fill(self, first_byte, length, used_pct, color=white):
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
            self._add_to_pixel_mix(color, used_pct, pct_of_pixel)
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
            self._add_to_pixel_mix(color, used_pct, pct_of_first_pixel)
            # all intermediate pixels are ours, set brightness directly
            if self.pos.linear < last_pixel - 1:
                self._next_pixel()
                self._add_to_pixel_mix(color, used_pct, pixel_pct=1)
                rgbytes = self._pixel_mix_to_rgbytes()
                self._set_pixel(rgbytes)
                if self.verbose >= 3:
                    print("        pixel range linear {} to {} rgb #{}".format(
                        self.pos.linear, last_pixel - 1,
                        ''.join('{:02x}'.format(ord(byte)) for byte in rgbytes)))
                while self.pos.linear < last_pixel - 1:
                    self._next_pixel()
                    self._set_pixel(rgbytes)
            self._next_pixel()
            # add our part of the last pixel, may be shared with next fill
            self._add_to_pixel_mix(color, used_pct, pct_of_last_pixel)

    def write_png(self, pngfile):
        print("pngfile {}".format(pngfile))
        if self._finished is False:
            if self._pixel_dirty is True:
                self._finish_pixel()
            self._finished = True
        if self.size > self.order:
            scale = 2 ** (self.size - self.order)
            rows = ((pix for pix in row for _ in range(scale))
                    for row in self._grid for _ in range(scale))
            _write_png(pngfile, self.width * scale, self.height * scale, rows)
        else:
            _write_png(pngfile, self.width, self.height, self._grid)


def walk_dev_extents(fs, devices=None, order=None, size=None,
                     default_granularity=33554432, verbose=0, min_brightness=None):
    if devices is None:
        devices = list(fs.devices())
        dev_extents = fs.dev_extents()
    else:
        if isinstance(devices, types.GeneratorType):
            devices = list(devices)
        dev_extents = (dev_extent
                       for device in devices
                       for dev_extent in fs.dev_extents(device.devid, device.devid))

    print("scope device {}".format(' '.join([str(device.devid) for device in devices])))
    total_bytes = 0
    device_grid_offset = {}
    for device in devices:
        device_grid_offset[device.devid] = total_bytes
        total_bytes += device.total_bytes

    grid = Grid(order, size, total_bytes, default_granularity, verbose, min_brightness)
    block_group_cache = {}
    for dev_extent in dev_extents:
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
        first_byte = device_grid_offset[dev_extent.devid] + dev_extent.paddr
        grid.fill(first_byte, dev_extent.length, used_pct,
                  dev_extent_colors[block_group.flags & btrfs.BLOCK_GROUP_TYPE_MASK])
    return grid


def walk_extents(fs, block_groups, order=None, size=None, default_granularity=None, verbose=0):
    if isinstance(block_groups, types.GeneratorType):
        block_groups = list(block_groups)
    fs_info = fs.fs_info()
    nodesize = fs_info.nodesize

    if default_granularity is None:
        default_granularity = fs_info.sectorsize

    print("scope block_group {}".format(' '.join([str(b.vaddr) for b in block_groups])))
    total_bytes = 0
    block_group_grid_offset = {}
    for block_group in block_groups:
        block_group_grid_offset[block_group] = total_bytes
        total_bytes += block_group.length

    grid = Grid(order, size, total_bytes, default_granularity, verbose)

    tree = btrfs.ctree.EXTENT_TREE_OBJECTID
    for block_group in block_groups:
        if verbose > 0:
            print(block_group)
        min_key = btrfs.ctree.Key(block_group.vaddr, 0, 0)
        max_key = btrfs.ctree.Key(block_group.vaddr + block_group.length, 0, 0) - 1
        for header, _ in btrfs.ioctl.search(fs.fd, tree, min_key, max_key):
            if header.type == btrfs.ctree.EXTENT_ITEM_KEY:
                length = header.offset
            elif header.type == btrfs.ctree.METADATA_ITEM_KEY:
                length = nodesize
            else:
                continue
            first_byte = block_group_grid_offset[block_group] + header.objectid - block_group.vaddr
            if verbose >= 1:
                print("extent vaddr {0} first_byte {1} type {2} length {3}".format(
                    header.objectid, first_byte, btrfs.ctree.key_type_str(header.type), length))
            grid.fill(first_byte, length, 1)
    return grid


def choose_order_size(order=None, size=None, total_bytes=None, default_granularity=None):
    order_was_none = order is None
    if order_was_none:
        import math
        order = min(10, int(math.ceil(math.log(math.sqrt(total_bytes/default_granularity), 2))))
    if size is None:
        size = 10
    if size < order:
        if order_was_none:
            order = size
        else:
            raise HeatmapError("size ({}) cannot be smaller than order ({})".format(size, order))
    return order, size


def generate_png_file_name(output=None, parts=None):
    if output is not None and os.path.isdir(output):
        output_dir = output
        output_file = None
    else:
        output_dir = None
        output_file = output
    if output_file is None:
        if parts is None:
            parts = []
        else:
            parts.append('at')
        import time
        parts.append(str(int(time.time())))
        output_file = '_'.join([str(part) for part in parts]) + '.png'
    if output_dir is None:
        return output_file
    return os.path.join(output_dir, output_file)


def _write_png(pngfile, width, height, rows):
    struct_len = struct_crc = struct.Struct('!I')
    out = open(pngfile, 'wb')
    out.write(b'\x89PNG\r\n\x1a\n')
    # IHDR
    out.write(struct_len.pack(13))
    ihdr = struct.Struct('!4s2I5B').pack(b'IHDR', width, height, 8, 2, 0, 0, 0)
    out.write(ihdr)
    out.write(struct_crc.pack(zlib.crc32(ihdr) & 0xffffffff))
    # IDAT
    length_pos = out.tell()
    out.write(b'\x00\x00\x00\x00IDAT')
    crc = zlib.crc32(b'IDAT')
    datalen = 0
    compress = zlib.compressobj()
    for row in rows:
        for uncompressed in (b'\x00', b''.join(row)):
            compressed = compress.compress(uncompressed)
            if len(compressed) > 0:
                crc = zlib.crc32(compressed, crc)
                datalen += len(compressed)
                out.write(compressed)
    compressed = compress.flush()
    if len(compressed) > 0:
        crc = zlib.crc32(compressed, crc)
        datalen += len(compressed)
        out.write(compressed)
    out.write(struct_crc.pack(crc & 0xffffffff))
    # IEND
    out.write(b'\x00\x00\x00\x00IEND\xae\x42\x60\x82')
    # Go back and write length of the IDAT
    out.seek(length_pos)
    out.write(struct_len.pack(datalen))
    out.close()


def main():
    args = parse_args()
    path = args.mountpoint
    verbose = args.verbose if args.verbose is not None else 0

    fs = btrfs.FileSystem(path)
    fs_info = fs.fs_info()
    print(fs_info)

    bg_vaddr = args.blockgroup
    if bg_vaddr is None:
        grid = walk_dev_extents(fs, order=args.order, size=args.size, verbose=verbose)
        filename_parts = ['fsid', fs.fsid]
    else:
        try:
            block_group = fs.block_group(bg_vaddr)
        except IndexError:
            raise HeatmapError("Error: no block group at vaddr {}!".format(bg_vaddr))
        grid = walk_extents(fs, [block_group], order=args.order, size=args.size, verbose=verbose)
        filename_parts = ['fsid', fs.fsid, 'blockgroup', block_group.vaddr]

    grid.write_png(generate_png_file_name(args.output, filename_parts))


if __name__ == '__main__':
    try:
        main()
    except HeatmapError as e:
        print("Error: {0}".format(e), file=sys.stderr)
        sys.exit(1)
