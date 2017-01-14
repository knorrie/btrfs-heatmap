Btrfs Heatmap
=============

The btrfs heatmap script creates a visualization of how a btrfs filesystem is
using the underlying raw disk space of the block devices that are added to it.

## What does it look like?

238GiB file system |
:--------------------------:|
![filesystem](doc/example-238gib.png)|


This picture shows the 238GiB filesystem in my computer at work. It was
generated using the command `./heatmap.py --size 9 /`, resulting in a 512x512
pixel png. The black parts are unallocated disk space. Raw disk space that is
allocated to be used for data (white), metadata (blue) or system (red) gets
brighter if the fill factor of block groups is higher.

## How do I create a picture like this of my own computer?

To run the program, you need to clone two git repositories:
* [btrfs-heatmap (this project)](https://github.com/knorrie/btrfs-heatmap.git)
* [python-btrfs (used to retrieve usage from btrfs)](https://github.com/knorrie/python-btrfs.git)

The fastest way to get it running is:
```
-$ git clone https://github.com/knorrie/btrfs-heatmap.git
-$ git clone https://github.com/knorrie/python-btrfs.git
-$ cd btrfs-heatmap
btrfs-heatmap (master) -$ ln -s ../python-btrfs/btrfs/
btrfs-heatmap (master) -$ sudo ./heatmap.py /mountpoint
```

When pointing heatmap.py to a mounted btrfs filesystem location, it will ask
the linux kernel for usage information and build a png picture reflecting that
low level information.

Because the needed information is retrieved using the btrfs kernel API, it has
to be run as root. :| If you don't trust it, don't run it on your system.

## Ok, I have a picture now, with quite a long filename, what do I see here?

The filename of the png picture is a combination of the filesystem ID and a
timestamp by default, so that if you create multiple of them, they nicely pile
up as input for creating a timelapse video.

The picture shows the usage of the physical disk space, like I explained above.
The ordering inside the picture is based on a [Hilbert
Curve](https://en.wikipedia.org/wiki/File:Hilbert_curve.svg). The lowest
physical address of the block devices is located in the bottom left corner.
From there it walks up, to the right and down again.

In technical btrfs terms speaking: The picture shows the physical address space
of a filesystem, by walking all dev extents of all devices in the filesystem
using the search ioctl and concatenating all information into a single big
image. The usage values are computed by looking up usage counters in the block
group items from the extent tree.

## A single picture is a bit boring...

Here's an example command to create an mp4 video out of all the png files if
you create multiple ones over time:
```
ffmpeg -framerate 2 -pattern_type glob -i '*.png' -c:v libx264 -r 25 -pix_fmt yuv420p btrfs-heatmap.mp4
```
By varying the `-framerate` option, you can make the video go faster or slower.

Another option is to create an animated gif. By varying the `-delay` option,
you change the speed.
```
convert -layers optimize-frame -loop 0 -delay 20 *.png btrfs-heatmap.gif
```

The next picture is an animated gif of running `btrfs balance` on the data of
the filesystem which the first picture was also taken of. You can see how all
free space is defragmented by packing data together:

btrfs balance |
:--------------------------:|
![animated gif balance](doc/animated-balance-small.gif)|

## More advanced usage

* [Extent level pictures](doc/extent.md) show detailed usage of the virtual
  address space inside block groups.
* By [scripting btrfs-heatmap](doc/scripting.md) it's possible to make pictures
  of single devices, or any combination of block groups.

## Feedback

Let me know if this program was useful for you, or if you have brilliant ideas
about how to improve it.

You can reach me on IRC in #btrfs on Freenode (I'm Knorrie), or send me an
email on hans@knorrie.org
