"""
Model for a person (author, editor, etc)
"""


import pywikibot


def get_name_string(name_item):
    return name_item.get()['claims']['P1705'][0].getTarget().text


def get_series_ordinal_index(c):
    try:
        q = c.qualifiers['P1545']
        return int(q[0].getTarget())
    except KeyError:
        pass

    return 1


class Author():

    def __init__(self):
        self.firstnames = []
        self.surname = ''
        self.commons_cats = []
        self.ws_page = None
        self.entity = None

    @staticmethod
    def get_first_last(item):

        claims = item.get()['claims']

        try:
            lastnames = claims['P734']
        except KeyError:
            lastnames = None

        if not lastnames or len(lastnames) != 1:
            raise ValueError(f'Can\'t determine surname for {item}')

        try:
            surname_target = lastnames[0].getTarget()
            surname = get_name_string(surname_target)
        except KeyError:
            raise ValueError(f'Can\'t get name string for {surname_target}')

        try:
            firstnames = claims['P735']
        except KeyError:
            firstnames = None

        if not firstnames:
            raise ValueError(f'No firstnames for item {item}')

        firstnames.sort(key=get_series_ordinal_index)
        firstnames = [get_name_string(c.getTarget()) for c in firstnames]

        return surname, firstnames

    @classmethod
    def from_wikidata(cls, item, lang):

        a = cls()
        a.entity = item

        claims = item.get()['claims']

        try:
            a.surname, a.firstnames = a.get_first_last(item)
        except ValueError:
            raise

        if 'P373' in claims:
            a.commons_cats += [c.getTarget() for c in claims['P373']]

        try:
            link = item.getSitelink(f'{lang}wikisource')
            a.ws_page = link
        except pywikibot.exceptions.NoPageError:
            a.ws_page = None

        return a

    @classmethod
    def from_string(cls, s):

        words = s.split()
        if len(words) <= 1:
            raise ValueError('Cannot guess name from {s}')

        a = cls()
        a.surname = words[-1]
        a.firstnames = words[:-1]

        return a

    def get_full_name(self):

        s = " ".join(self.firstnames)

        if self.surname:
            s += " " + self.surname
        return s
