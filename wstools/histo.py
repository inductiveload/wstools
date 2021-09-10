#! /usr/bin/env python3

import argparse
import logging

import cv2
import numpy
from matplotlib import pyplot as plt


def greyscale_histogram(image_file):

    img = cv2.imread(image_file, 0)
    hist = cv2.calcHist([img], [0], None, [256], [0, 256])

    return hist


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--image', required=True,
                        help='The image')
    parser.add_argument('-o', '--output-file',
                        help='The output image, - for stdout')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    hist = greyscale_histogram(args.image)

    # with numpy.errstate(divide='ignore'):
    #     hist = numpy.log10(hist, where=hist > 0)

    print(hist)

    plt.bar([i for i in range(len(hist))], hist[0])
    # plt.xlim([0, 256])

    if args.output_file:
        if args.output_file != "-":
            plt.savefig(args.output_file)
        else:
            raise NotImplementedError
    else:
        plt.show()


if __name__ == "__main__":
    main()
