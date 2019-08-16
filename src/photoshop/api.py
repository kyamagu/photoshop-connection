"""
Kevlar API wrappers.

https://github.com/adobe-photoshop/generator-core/wiki/Photoshop-Kevlar-API-Additions-for-Generator
"""
from jinja2 import Environment, PackageLoader
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
env = Environment(loader=PackageLoader('photoshop', 'api'), trim_blocks=True)


class Kevlar(object):
    def get_document_thumbnail(
        self,
        document=None,
        max_width=2048,
        max_height=2048,
        format=1,
        placed_ids=[]
    ):
        """
        :param document: optional document id, uses active doc if not specified.
        :param max_width: maximum width of thumbnail.
        :param max_height: maximum height of thumbnail.
        :param format: 1 is JPEG, 2 is pixmap (uncompressed w/ transparency).
        :param placed_ids: Photoshop 16.1 and later, optional. reference smart
            object(s) within the document series of "ID" from
            layer:smartObject:{} or "placedID" from "image:placed:[{}]"
        :param: JPEG bytes if format is 1, or Pixmap object if format is 2.
        """
        template = env.get_template('sendDocumentThumbnailToNetworkClient.js')
        return self.execute(template.render(locals())).get('body').get('data')
