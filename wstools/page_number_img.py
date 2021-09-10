#! /usr/bin/env python3

import argparse
import logging

import subprocess


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    pn = 1
    for i in range(11, 180):

        fn = "/tmp/ys/out-1/ys_-{:03}.tif".format(i)
        ofn = "/tmp/ys/out-1n/ys_-{:03}.png".format(i)
        ofn2 = "/tmp/ys/out-1m/ys_-{:03}.pbm".format(i)

        cmd = ["convert", fn, "-gravity", "south",
               "-fill", "black",
               "-pointsize", "150",
               "-font", "Arial",
               "-annotate", "+0+350",
               "{}".format(pn),
               ofn
               ]

        print(cmd)
        subprocess.call(cmd)

        cmd = ["convert", ofn, ofn2]
        subprocess.call(cmd)

        pn += 1


if __name__ == "__main__":
    main()