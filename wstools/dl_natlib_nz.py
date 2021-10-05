#! /usr/bin/env python3

import argparse
import logging
import base64
import requests
import dotenv
import os
import time
import random


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    dotenv.load_dotenv()

    OUT_DIR = os.getenv('WSTOOLS_OUTDIR')

    BASE = "https://paperspast.natlib.govt.nz/imageserver/periodicals/"

    sess = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:92.0) Gecko/20100101 Firefox/92.0"
    }

    sess.headers.update(headers)

    id = 'TPRSNZ1876-9.1'
    ext = 'jpg'
    width = None

    dl_dir = os.path.join(OUT_DIR, id)

    os.makedirs(dl_dir, exist_ok=True)

    for pgnum in range(744, 810 + 1):

        delay = random.uniform(20, 35)

        while True:

            logging.debug(f'File number: {pgnum}')

            s = f'?oid={id}.{pgnum}&colours=all&ext={ext}'

            if width:
                s += f'&width={width}'

            url = BASE + base64.b64encode(s.encode('utf8')).decode('utf8')

            logging.debug(f'{url}')

            r = sess.get(url)
            r.raise_for_status()

            fn = os.path.join(dl_dir, f'{pgnum:04}.{ext}')

            if r.content[0] != 0xff:
                logging.info('Failed, retrying')
                delay *= 2
                time.sleep(delay)
                continue

            with open(fn, 'wb') as ofile:
                ofile.write(r.content)

            break

        time.sleep(delay)


if __name__ == "__main__":
    main()
