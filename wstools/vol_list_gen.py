#! /usr/bin/env python3

import argparse
import logging


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)


    for i in range(1, 30):

        print("* [[/Volume {}/]] ({}) {{{{small scan link|Hardwicke's Science-Gossip - Volume {}.pdf}}}}".format(
            i, 1864 + i, i))


if __name__ == "__main__":
    main()

    