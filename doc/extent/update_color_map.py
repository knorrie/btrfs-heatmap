#!/usr/bin/python

import heatmap
import btrfs

height = 25
width = 100
for color in heatmap.metadata_extent_colors:
    pngfile = "doc/%s.png" % btrfs.ctree._key_objectid_str_map[color]
    print(pngfile)
    bcolor = heatmap.struct_color.pack(*heatmap.metadata_extent_colors[color])
    rows = ((bcolor for _ in range(width))
            for _ in range(height))
    heatmap._write_png(pngfile, width, height, rows)
