Btrfs Heatmap
=============

The btrfs heatmap script creates a visualization of how a btrfs filesystem is using the underlying raw disk space of the block devices that are added to it.

## What does it look like?

![238GiB filesystem](doc/example-238gib.png)

This picture shows the 238GiB filesystem in my computer at work. The black parts are unallocated disk space. Raw disk space that is allocated to be used for data or metadata gets brighter if the fill factor is higher.

```
Label: none  uuid: ed10a358-c846-4e76-a071-3821d423a99d
    Total devices 1 FS bytes used 132.74GiB
    devid    1 size 237.54GiB used 152.01GiB path /dev/mapper/sda2_crypt
```

The filesystem has 152.01GiB of the 237.54GiB allocated, in which actually only 132.74GiB is used. The picture gives an idea about the distribution of that data inside the allocated space.

The ordering inside the picture is based on a [Hilbert Curve](https://en.wikipedia.org/wiki/File:Hilbert_curve.svg). The lowest physical address of the block devices is located in the bottom left corner. From there it walks up, to the right and down again.

## How?

Besides the code in here, there are two extra dependencies:

 * [python-btrfs](https://github.com/knorrie/python-btrfs), used to gather all usage information
 * [png.py from the pypng project](https://github.com/drj11/pypng/blob/master/code/png.py), used to write the png image


```
-# ./heatmap.py --help
usage: heatmap.py [-h] [--curve {hilbert,linear}] [--order ORDER]
                  [--size SIZE] [-v] [-o PNGFILE]
                  mountpoint

positional arguments:
  mountpoint            Btrfs filesystem mountpoint

optional arguments:
  -h, --help            show this help message and exit
  --curve {hilbert,linear}
                        Space filling curve type (default: hilbert)
  --order ORDER         Hilbert curve order (default: automatically chosen)
  --size SIZE           Image size (default: 10). Height/width is 2^size
  -v, --verbose         increase debug output verbosity
  -o PNGFILE, --output PNGFILE
                        Output png file name
```

Creating an image can be done by pointing `heatmap.py` to a mounted filesystem, for example `./heatmap.py -o home.png /home`. Because the needed information is retrieved using the btrfs kernel API, it has to be run as root. :|

## Why?

Well, it's fun. But it gets more fun when you take multiple pictures and compare them, for example before and after playing around with `btrfs balance`. Or, set up a cron job which generates a timestamped picture every day and then turn them into a movie that shows data being added, removed and moved around in your filesystem.

Here's an example of a video of a 2TiB filesystem (links to a video on youtube):

[![heatmap video](http://img.youtube.com/vi/Qj1lxAasytc/0.jpg)](https://youtu.be/Qj1lxAasytc)

The command used to create an mp4 video out of all the pngs:

```
ffmpeg -framerate 2 -pattern_type glob -i '*.png' -c:v libx264 -r 30 -pix_fmt yuv420p out.mp4
```
