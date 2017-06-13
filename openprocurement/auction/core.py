from zope.interface import implementer
from pkg_resources import iter_entry_points

import logging

from .components import components
from .interfaces import IFeedItem, IAuctionDatabridge,\
    IAuctionManager, IWorkerCmdFactory


PKG_NAMESPACE = "openprocurement.auction.plugins"
LOGGER = logging.getLogger(__name__)


@components.adapter(
    provides=IWorkerCmdFactory, adapts=(IAuctionDatabridge, IFeedItem)
)
@implementer(IAuctionManager)
class AuctionManager(object):

    def __init__(self, databridge, feed):
        self.databridge = databridge
        self.feed_item = feed
        plugins = self.databridge.config_get('plugins') or []

        # TODO: check me
        for entry_point in iter_entry_points(PKG_NAMESPACE):
            LOGGER.info("Loading {} plugin".format(entry_point.name))
            plugin = entry_point.load()
            plugin(components)

    def __call__(self):

        auction_iface = components.match(self.feed_item)
        if not auction_iface:
            # print "{} skipped".format(self.feed_item.get('procurementMethodType'))
            return None
        return components.queryMultiAdapter(
            (self.databridge, self.feed_item),
            auction_iface
        )
