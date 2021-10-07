
import requests
from requests_oauthlib import OAuth1
import urllib.parse
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import time

import os


class DataAPI(object):

    def __init__(self, client_key=None, client_secret=None,
                 secure=True, proxies=None):
        """ Initialize a DataAPI object.
        Args:
            client_key: OAuth client key (registered with HathiTrust)
            client_secret: secret OAuth key
            secure: toggles http/https session. Defaults to
                 http, use https for access to restricted content.
        Initializes a persistent Requests session and attaches
        OAuth credentials to the session. All queries are performed as
        method calls on the HTDataInterface object.
        For now, all queries return the raw content string, rather than
        processing the json or xml structures.
        """

        if not client_key:
            client_key = os.getenv('HATHI_DAPI_CLIENT_KEY')

        if not client_secret:
            client_secret = os.getenv('HATHI_DAPI_CLIENT_SECRET')

        if proxies is True:
            # auto-lookup
            proxies = {
              'http': os.getenv('HATHI_DAPI_HTTP_PROXY'),
              'https': os.getenv('HATHI_DAPI_HTTPS_PROXY'),
            }

        print(proxies)

        self.client_key = client_key
        self.client_secret = client_secret
        self.oauth = OAuth1(client_key=client_key,
                            client_secret=client_secret,
                            signature_type='query')

        self.max_retries = 5
        self.delay_on_retry = 12

        self.rsession = requests.Session()

        self.rsession.headers.update({
            "user-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36"
        })

        if proxies:
            self.rsession.proxies.update(proxies)

        retry = Retry(total=5,
                      backoff_factor=5,
                      status_forcelist=[401, 429])

        self.rsession.mount('http://', HTTPAdapter(max_retries=retry))
        self.rsession.mount('https://', HTTPAdapter(max_retries=retry))

        self.rsession.auth = self.oauth

        self.baseurl = "http"
        if secure:
            self.baseurl += "s"

        self.baseurl += '://babel.hathitrust.org/cgi/htd/'

    def _makerequest(self, resource, doc_id, doc_type='volume', sequence=None,
                     v=2, json=False, callback=None, params=None):
        """ Construct and perform URI request.
        Args:
            resource: resource type
            doc_id: document identifier of target
            doc_type: type of document: volume or article
            sequence: page number for single page resources
            v: API version
            json: if json=True, the json representation of
                the resource is returned. Only valid for resources that
                are xml or xml+atom by default.
            callback: optional javascript callback function,
                which only has an effect if json=True.
        Return:
            content of the response, in bytes
        Note there's not much error checking on url construction,
        but errors do get raised after badly formed requests.
        To do: implement some exception checking here, and identify
        what sort of errors are being returned (eg. BadRequest,
        Unauthorized, NotFound, etc.)
        """

        if doc_type:
            doc_type = '%s/' % doc_type

        enc_id = urllib.parse.quote(doc_id)

        url = "".join([self.baseurl, doc_type, resource, '/', enc_id])

        if sequence:
            url += '/' + str(sequence)

        if params is None:
            params = {}

        params['v'] = str(v)

        if json:
            params['format'] = 'json'
            if callback:
                params['callback'] = callback

        print(url)

        r = self.rsession.get(url, params=params)
        r.raise_for_status()
        return r

    def getmeta(self, doc_id, doc_type='volume', json=False):
        """ Retrieve Volume and Rights Metadata resources.
        Args:
            doc_id: document identifier
            json: if json=True, the json representation of
                the resource is returned, otherwise efaults to an atom+xml
                format.
        Return:
            xml or json string
        """
        r = self._makerequest('meta', doc_id, doc_type=doc_type, json=json)
        return r.content

    def getstructure(self, doc_id, doc_type='', json=False):
        """ Retrieve a METS document.
        Args:
            doc_id: target document
            json: toggles json/xml
        Return:
            xml or json string
        """
        r = self._makerequest('structure', doc_id, doc_type=doc_type,
                              json=json)
        return r.content

    def get_image(self, doc_id, sequence, format='optimalderivative',
                  resolution=0):

        params = {
            'format': format,
            'res': resolution,
        }

        retries = 0

        while True:
            try:

                r = self._makerequest('pageimage', doc_id, sequence=sequence,
                                      params=params)
                return r.content, r.headers['content-type']
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code

                if retries < self.max_retries and status_code in [503, 429]:
                    retries += 1
                    time.sleep(self.delay_on_retry)
                    continue

                raise

    def get_ocr(self, doc_id, sequence):
        r = self._makerequest('pageocr', doc_id, sequence=sequence, json=False)
        return r.content

    def get_coord_ocr(self, doc_id, sequence):
        r = self._makerequest('pagecoordocr', doc_id, sequence=sequence, json=False)
        return r.content
