
import utils.source

import urllib.parse

class UrlSource(utils.source.Source):

  def __init__(self, url) -> None:
    super().__init__()
    self.url = url

  def can_download_file(self):
    return True

  def get_id(self):
    return self.url

  def download(self, proxy):

    if proxy:
      raise NotImplementedError

    return utils.source.get_from_url(
      self.url, session=None,
      name=None,
      chunk_size=1024*1024*1
    )

  def get_file_name(self):
    url = urllib.parse.urlparse(self.url)
    return url.path.split('/')[-1]