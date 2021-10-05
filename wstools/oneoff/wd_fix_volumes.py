#! /usr/bin/env python3
# Fix items using scientific journal wrong

import argparse
import logging

import pywikibot
import pywikibot.data.sparql

SPARQL = """
SELECT DISTINCT ?item WHERE {
  ?item p:P31 [ ps:P31 wd:Q1238720 ].
  ?item p:P31 [ ps:P31 wd:Q5633421 ].
}
"""

ITEMS = [
    # "Q104539312",
    "Q105369310",
    "Q104550933",
    "Q104538509",
    "Q104547307",
    "Q104551298",
    "Q104549409",
    "Q104531675",
    "Q104535721",
    "Q104531984",
    "Q104531138",
]

QIDS = {
    "scientific journal": "Q5633421",
    "volume": "Q1238720",
    "periodical volume": "Q108804797"
}


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    qy = pywikibot.data.sparql.SparqlQuery()

    pywikibot.config.put_throttle = 1

    res = ITEMS  # qy.get_items(SPARQL)

    site = pywikibot.Site('en', 'wikisource')
    repo = site.data_repository()

    for qid in res:

        item = pywikibot.ItemPage(repo, qid)  # This will be functionally the same as the other item we defined

        if item.claims:
            if 'P31' in item.claims:  # instance of

                for claim in item.claims['P31']:
                    if claim.getTarget().id == QIDS['scientific journal']:

                        item.removeClaims(
                                claim,
                                bot=False,
                                summary="Volumes are not, in and of themselves, scientific journals; they are ''part of'' a journal")

                    elif claim.getTarget().id == QIDS['volume']:

                        claim.changeRank(
                                'normal',
                                bot=False,
                                summary="This should be normal rank.")


if __name__ == "__main__":
    main()
