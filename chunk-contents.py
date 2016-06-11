#!/usr/bin/python

import btrfs
import os
import sys

filenames_cache = {}

def get_chunk_length(fd, vaddr):
    chunks = btrfs.search(fd,
                          tree=btrfs.CHUNK_TREE_OBJECTID,
                          objid=btrfs.FIRST_CHUNK_TREE_OBJECTID,
                          key_type=btrfs.CHUNK_ITEM_KEY,
                          offset=(vaddr, vaddr),
                          structure=btrfs.chunk)

    if len(chunks) != 1:
        raise Exception("Not 1, but %s chunks found at vaddr %s" % (len(chunks), vaddr))
    header, buf, chunk = chunks[0]
    length = chunk[0]
    return length


def list_extents(fd, min_vaddr, chunk_length):
    max_vaddr = min_vaddr + chunk_length - 1
    vaddrlen = str(len(str(max_vaddr)))
    format_string = ''.join(("%", vaddrlen, "s %", vaddrlen, "s %9s %.2f%% %s"))
    next_vaddr = min_vaddr
    while True:
        if min_vaddr > max_vaddr:
            break
        extents = btrfs.search(fd,
                               tree=btrfs.EXTENT_TREE_OBJECTID,
                               objid=(min_vaddr, max_vaddr),
                               )
        if len(extents) == 0:
            break

        for header, buf, _ in extents:
            _, extent_vaddr, extent_size, key_type, _ = header
            if key_type != btrfs.EXTENT_ITEM_KEY:
                if key_type != btrfs.BLOCK_GROUP_ITEM_KEY:
                    print("What's this thing? %s" % header)
                continue
            min_vaddr = extent_vaddr + 1
            if extent_vaddr > next_vaddr:
                print(format_string %
                      (next_vaddr, extent_vaddr - 1,
                       extent_vaddr - next_vaddr,
                       float(extent_vaddr - next_vaddr) / chunk_length * 100,
                       ""))
            next_vaddr = extent_vaddr + extent_size
            print(format_string %
                  (extent_vaddr, extent_vaddr + extent_size - 1,
                   extent_size,
                   float(extent_size) / chunk_length * 100,
                   "extent item"))
            pos = 0
            refs, gen, flags = btrfs.extent_item.unpack_from(buf, pos)
            pos = pos + btrfs.extent_item.size
            print("\textent refs %s gen %s flags %s" %
                  (refs, gen, btrfs.extent_flags_to_str(flags)))
            if flags & btrfs.EXTENT_FLAG_TREE_BLOCK:
                print("Bork, EXTENT_FLAG_TREE_BLOCK")
                continue
            # assume no metadata, skip tree_block logic, directly assume iref on pos
            iref_type, iref_offset = btrfs.extent_inline_ref.unpack_from(buf, pos)
            if iref_type == btrfs.EXTENT_DATA_REF_KEY:
                pos = pos + 1
                while pos < len(buf):
                    dref_root, dref_objectid, dref_offset, dref_count = \
                        btrfs.extent_data_ref.unpack_from(buf, pos)
                    filenames = filenames_cache.get((dref_root, dref_objectid),
                                                    find_filenames(fd, dref_root, dref_objectid))
                    print("\textent data backref root %s objectid %s names %s" %
                          (dref_root, dref_objectid, filenames))
                    pos = pos + btrfs.extent_data_ref.size

    if next_vaddr < max_vaddr:
        print(format_string %
              (next_vaddr, max_vaddr,
               max_vaddr + 1 - next_vaddr,
               float(max_vaddr + 1 - next_vaddr) / chunk_length * 100,
               ""))


def find_filenames(fd, root, inode):
    inode_refs = btrfs.search(fd, tree=root, objid=inode,
                              key_type=btrfs.INODE_REF_KEY,
                              )
    if len(inode_refs) > 1:
        raise Exception("Not exactly 1 inode_ref found, but %s for root %s inode %s" %
                        (len(inode_refs), root, inode))

    if len(inode_refs) == 0:
        filenames_cache[(root, inode)] = None
        return None

    names = []
    _, buf, _ = inode_refs[0]
    pos = 0
    while pos < len(buf):
        index, namelen = btrfs.inode_ref.unpack_from(buf, pos)
        pos = pos + btrfs.inode_ref.size
        name = buf[pos:pos+namelen].tostring()
        names.append(name)
        pos = pos + namelen
    filenames_cache[(root, inode)] = names
    return names


def main():
    vaddr = int(sys.argv[1])
    fd = os.open(sys.argv[2], os.O_RDONLY)
    length = get_chunk_length(fd, vaddr)
    print("chunk vaddr %s length %s" % (vaddr, length))
    list_extents(fd, vaddr, length)
    os.close(fd)


if __name__ == '__main__':
    main()
