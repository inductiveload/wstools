#! /usr/bin/env python3

import argparse
import logging


import inotify.adapters
import subprocess
import os
import dotenv


dotenv.load_dotenv()

DEV = os.getenv('SEND_EBOOK_DEV')
PATH_ON_DEV = os.getenv('SEND_EBOOK_PATH_ON_DEV')
LOCAL_PATH = os.getenv('SEND_EBOOK_LOCAL_PATH')


def send_file(file):

    logging.info("Sending file: {}".format(file))
    cmd = ["scp", file, "{}:{}".format(DEV, PATH_ON_DEV)]
    subprocess.call(cmd)


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    i = inotify.adapters.Inotify()

    i.add_watch(LOCAL_PATH)

    for event in i.event_gen(yield_nones=False):
        (x, type_names, path, filename) = event

        if 'IN_CLOSE_WRITE' in type_names:
            # print("PATH=[{}] FILENAME=[{}] EVENT_TYPES={} X={}".format(
            #       path, filename, type_names,))

            # reject firefox partial downloads
            if not filename.endswith(".part"):
                send_file(os.path.join(path, filename))


if __name__ == "__main__":
    main()
