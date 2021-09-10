
import subprocess


def get_bitdepth(tiff_file):

    cmd = ["tiffinfo", tiff_file]

    out = subprocess.check_output(cmd).decode()

    bps = [x for x in out.split("\n") if x.startswith("  Bits/Sample:")][0]
    bps = int(bps.split(":")[-1].strip())

    return bps
