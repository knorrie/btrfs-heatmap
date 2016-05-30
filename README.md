BTRFS Heatmap
=============

Disclaimer: Proof of concept level code.

Running `show_usage.py` on a mountpoint will show btrfs devices, chunks and their usage

Use `makepng.py` (clone https://github.com/drj11/pypng.git) on the file to make a png image

    ./show_usage.py / | ./makepng.py

Do it everyday, store the results and use ffmpeg to make a movie from the pngs :o)

No support for RAID0 and even fancier things yet.
