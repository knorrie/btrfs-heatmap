#!/usr/bin/python

import btrfs
import fcntl
import os


def df(fd):
    space_args = btrfs.sized_array(btrfs.ioctl_space_args.size)
    fcntl.ioctl(fd, btrfs.IOC_SPACE_INFO, space_args)
    _, total_spaces = btrfs.ioctl_space_args.unpack(space_args)
    space_info_buf_size = btrfs.ioctl_space_args.size + btrfs.ioctl_space_info.size * total_spaces
    space_info = btrfs.sized_array(space_info_buf_size)
    btrfs.ioctl_space_args.pack_into(space_info, 0, total_spaces, 0)
    fcntl.ioctl(fd, btrfs.IOC_SPACE_INFO, space_info)
    for offset in xrange(btrfs.ioctl_space_args.size,
                         space_info_buf_size,
                         btrfs.ioctl_space_info.size):
        flags, total, used = btrfs.ioctl_space_info.unpack_from(space_info, offset)
        print("flags: %s, size: %s, used: %s" % (flags, total, used))


def devices(fd):
    devices = btrfs.search(fd,
                           tree=btrfs.CHUNK_TREE_OBJECTID,
                           objid=btrfs.DEV_ITEMS_OBJECTID,
                           key_type=btrfs.DEV_ITEM_KEY,
                           structure=btrfs.dev_item)
    for header, buf, device in devices:
        print("dev item devid %s total bytes %s bytes used %s" % (device[0], device[1], device[2]))


def chunks(fd):
    chunks = btrfs.search(fd,
                          tree=btrfs.CHUNK_TREE_OBJECTID,
                          objid=btrfs.FIRST_CHUNK_TREE_OBJECTID,
                          key_type=btrfs.CHUNK_ITEM_KEY,
                          structure=btrfs.chunk)
    for header, buf, chunk in chunks:
        num_stripes = chunk[7]
        pos = btrfs.chunk.size
        for i in xrange(num_stripes):
            stripe = btrfs.stripe.unpack_from(buf, pos)
            pos += btrfs.stripe.size
            print("chunk type %s devid %s offset %s length %s" %
                  (chunk[3], stripe[0], stripe[1], chunk[0]))


def main():
    fd = os.open("/mnt/heatmap", os.O_RDONLY)
    df(fd)
    devices(fd)
    chunks(fd)
    os.close(fd)


if __name__ == '__main__':
    main()
