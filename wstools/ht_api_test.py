#! /usr/bin/env python3

import argparse
import logging

import json

import utils.ht_api as HTAPI
import utils.pagelist as PL


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--id',
                        help='Hathi work ID')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    dapi = HTAPI.DataAPI()
    r = dapi.getmeta(args.id, json=True)

    data = json.loads(r)

    pl = PL.PageList()

    for seq in data['htd:seqmap'][0]['htd:seq']:

        if seq['htd:pnum']:
            pn = seq['htd:pnum']
        else:
            pn = '–'

        # print(seq['pseq'], pn)
        pl.append(pn)

    print(pl.to_str())

    # for seq in data['htd:seqmap']['htd:seq']:

    #     print(seq)
    #     break
        # print(seq.attrib['pseq'], seq['htd:pnum'])


if __name__ == "__main__":
    main()
