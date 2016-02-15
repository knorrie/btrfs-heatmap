#!/usr/bin/python

import btrfs
import os
import sys


def devices(fd):
    devices = btrfs.search(fd,
                           tree=btrfs.CHUNK_TREE_OBJECTID,
                           objid=btrfs.DEV_ITEMS_OBJECTID,
                           key_type=btrfs.DEV_ITEM_KEY,
                           structure=btrfs.dev_item)
    for header, buf, device in devices:
        print("dev item devid %s total bytes %s bytes used %s" % (device[0], device[1], device[2]))


def chunks(fd):
    offset = (0, btrfs.MINUS_ONE)
    while True:
        print("; searching chunks, offset %s" % offset[0])
        chunks = btrfs.search(fd,
                              tree=btrfs.CHUNK_TREE_OBJECTID,
                              objid=btrfs.FIRST_CHUNK_TREE_OBJECTID,
                              key_type=btrfs.CHUNK_ITEM_KEY,
                              offset=offset,
                              structure=btrfs.chunk)
        for header, buf, chunk in chunks:
            num_stripes = chunk[7]
            pos = btrfs.chunk.size
            vaddr = header[2]
            offset = (vaddr + 1, btrfs.MINUS_ONE)
            used = block_group_used_for_chunk(fd, vaddr)
            for i in xrange(num_stripes):
                stripe = btrfs.stripe.unpack_from(buf, pos)
                pos += btrfs.stripe.size
                print("chunk vaddr %s type %s stripe %s devid %s offset %s length %s used %s" %
                      (vaddr, chunk[3], i, stripe[0], stripe[1], chunk[0], used))

        if len(chunks) == 0:
            break


def block_group_used_for_chunk(fd, vaddr):
    block_groups = btrfs.search(fd,
                                tree=btrfs.EXTENT_TREE_OBJECTID,
                                objid=vaddr,
                                key_type=btrfs.BLOCK_GROUP_ITEM_KEY,
                                structure=btrfs.block_group_item)
    if len(block_groups) > 1:
        raise Exception("Apparently I have no idea what I'm doing!")
    return block_groups[0][2][0]


def main():
    fd = os.open(sys.argv[1], os.O_RDONLY)
    devices(fd)
    chunks(fd)
    os.close(fd)


if __name__ == '__main__':
    main()
