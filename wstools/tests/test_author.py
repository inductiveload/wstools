import utils.author

import pywikibot

REPO = pywikibot.Site('wikidata', 'wikidata').data_repository()


def inc(x):
    return x + 1


def test_wikidata():
    item = pywikibot.ItemPage(REPO, "Q16743442")
    author = utils.author.Author.from_wikidata(item, 'en')

    assert author.surname == 'Bettany'
    assert author.firstnames == ['George', 'Thomas']

    assert author.get_full_name() == 'George Thomas Bettany'

    assert author.commons_cats == ['George Thomas Bettany']


def test_from_string():

    author = utils.author.Author.from_string('George Thomas Bettany')

    assert author.surname == 'Bettany'
    assert author.firstnames == ['George', 'Thomas']
    assert author.get_full_name() == 'George Thomas Bettany'
