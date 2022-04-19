
import utils.source

import urllib.parse

import re
import requests

def get_filename_from_cd(cd):
    """
    Get filename from Content-Disposition header
    """
    if not cd:
        return None

    fname = re.findall(r'filename(?:=|\*=.*\'\')(.+)', cd)
    if len(fname) > 0:
        return fname[0]
   
    return None

class UrlSource(utils.source.Source):

  def __init__(self, url) -> None:
    super().__init__()
    self.url = url
    self.session = requests.Session()

  def can_download_file(self):
    return True

  def get_id(self):
    return self.url

  def download(self, proxy):
    if proxy:
      raise NotImplementedError

    return utils.source.get_from_url(
      self.url, session=self.session,
      name=None,
      chunk_size=1024*1024*1
    )

  def get_file_name(self):

    r = self.session.head(self.url)

    name = None
    if 'Content-Disposition' in r.headers:
      name = get_filename_from_cd(r.headers['Content-Disposition'])

    if not name:
      url = urllib.parse.urlparse(self.url)
      name = url.path.split('/')[-1]
    
    return name