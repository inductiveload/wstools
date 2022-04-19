"""
Utils for WS local settings
"""

FIELD_MAP = {
    'en': {
        'params': {
            'type': 'Type',
            'title': 'Title',
            'lang': 'Language',
            'volume': 'Volume',
            'author': 'Author',
            'translator': 'Translator',
            'editor': 'Editor',
            'illustrator': 'Illustrator',
            'school': 'School',
            'publisher': 'Publisher',
            'printer': 'None',
            'city': 'Address',
            'year': 'Year',
            'key': 'Key',
            'isbn': 'ISBN',
            'oclc': 'OCLC',
            'lccn': 'LCCN',
            'bnf_ark': 'BNF_ARK',
            'arc': 'ARC',
            'source': 'Source',
            'image': 'Image',
            'progress': 'Progress',
            'pages': 'Pages',
            'volumes': 'Volumes',
            'remarks': 'Remarks',
            'valid_date': 'Validation date',
            'transclusion': 'Transclusion',
            'wikidata': 'Wikidata',
            'css': 'Css',
            'header': 'Header',
            'footer': 'Footer',
            'width': 'Width',
        },
        'index_formats': {
            'title': "''{}''"
        },
        'filename_formats': {
           'volume': 'Volume {}',
           'issue': 'Number {}',
        },
        'source_formats': {
            'ia': '{{{{IA|{id}}}}}',
            'ht': '{{{{HathiTrust|{id}|book}}}}',
        },
        'licenses': {
            'auto_pma': {
                'title' :'PD/US',
                'deathyear': 'deathyear'
            }
        },
        'defaults': {
            'progress': 'X',
            'transclusion': 'no',
            'type': 'book',
        },
        'field_order': [
            'type', 'title', 'lang', 'volume', 'author', 'editor',
            'translator', 'illustrator', 'publisher',  # 'printer',
            'city', 'year', 'key', 'isbn', 'oclc', 'lccn', 'bnk_ark',
            'arc', 'source', 'image',
            'progress', 'transclusion', 'valid_date', 'pages',
            'remarks', 'wikidata', 'volumes',
            'width', 'css', 'header', 'footer'
        ]
    },
    'es': {
        'params': {
            'title': 'Titulo',
            'subtitle': 'Subtitulo',
            'lang': 'Idioma',
            'volume': 'Volumen',
            'author': 'Autor',
            'translator': 'Traductor',
            'editor': 'Editor',
            'illustrator': 'Ilustrador',
            'publisher': 'Editorial',
            'printer': 'Imprenta',
            'city': 'Lugar',
            'file_source': 'Fuente',
            'year': 'Ano',
            'key': 'Key',
            'image': 'Imagen',
            'progress': 'Progreso',
            'pages': 'Paginas',
            'volumes': 'Serie',
            'remarks': 'Notas',
            'wikidata': 'Wikidata',
            'country': 'derechos',
            'header': 'Header',
            'footer': 'Footer',
        },
        'filename_formats': {
           'volume': 'Tomo {}'
        },
        'source_formats': {
            'ia': '{{{{IA|{id}}}}}',
            'ht': '{{{{HathiTrust|{id}}}}}',
        },
        'defaults': {
            'progress': 'C'
        },
        'field_order': [
            'title', 'subtitle', 'lang', 'volume', 'author', 'editor',
            'translator', 'publisher', 'printer', 'city', 'illustrator',
            'year', 'country', 'file_source', 'image',
            'progress', 'pages', 'remarks', 'wikidata', 'volumes',
            'header', 'footer'
        ]
    },
    'mul': {
        'params': {
            'title': 'Title',
            'lang': 'Language',
            'author': 'Author',
            'translator': 'Translator',
            'editor': 'Editor',
            'publisher': 'Publisher',
            'city': 'Address',
            'year': 'Year',
            'key': 'Key',
            'source': 'Source',
            'image': 'Image',
            'progress': 'Progress',
            'pages': 'Pages',
            'volumes': 'Volumes',
            'remarks': 'Remarks',
            'valid_date': 'Validation date',
            'css': 'Css',
            'width': 'Width',
        },
        'index_formats': {
        },
        'filename_formats': {
           'volume': 'Volume {}',
           'issue': 'Number {}',
        },
        'source_formats': {
            'ia': '{{{{IA|{id}}}}}',
            'ht': '{{{{HathiTrust|{id}|book}}}}',
        },
        'defaults': {
            'progress': 'C'
        },
        'field_order': [
            'title', 'lang', 'author', 'translator', 'editor',
            'year', 'publisher',  # 'printer',
            'city', 'key', 'source', 'image',
            'progress', 'volumes', 'pages',
            'remarks',
            'width', 'css'
        ]
    }
}

class WsLocal:

    def __init__(self, lang):
        self.lang = lang

    def get_index_field_map(self):
        return FIELD_MAP[self.lang]['params']

    def get_index_field_default(self, field):
        return FIELD_MAP[self.lang]['defaults'][field]

    def get_filename_format_strings(self):

        return FIELD_MAP[self.lang]['filename_formats']

    def format_filename_part(self, part, value):
        formats = FIELD_MAP[self.lang]['filename_formats']
        # need to implement
        return formats[part].format(value.strip())

    def format_source(self, source_key, source_id):
        return FIELD_MAP[self.lang]['source_formats'][source_key].format(id=source_id)

    def format_index_field(self, field, value):
        field_map = self.get_index_field_map()
        #use a formatter if there is one
        if 'index_formats' in field_map and field in field_map['index_formats']:
            value = field_map['index_formats'][field].format(value.strip())
        else:
            value = value.strip()

        return value

    def get_auto_pma_license(self):
        auto_pma_info = FIELD_MAP['licenses']['auto-pma']
        return auto_pma_info['title'], auto_pma_info['deathyear']
