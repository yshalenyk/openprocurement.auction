from zope.interface import implementer

from .components import components
from .interfaces import IFeedItem, IAuctionDatabridge,\
    IAuctionManager, IWorkerFactory, IWorkerCommand


DEFAULT_PROCUREMENT_METHOD_TYPES = [
    
]

@components.component()
@implementer(IWorkerFactory)
class AuctionManager(object):

    def __init__(self, databridge, feed):
        self.databridge = databridge
        self.feed_item = feed

    def __call__(self):
        # TODO: check me
        for ut in list(components.getUtilitiesFor(IWorkerCmd)):
            if ut.match(self.feed_item):
                return iter(ut(self.feed_item))


@components.adapter(
    provides=IWorkerFactory, adapts=(IAuctionDatabridge, IFeedItem)
)
@implementer(IWorkerCommand)
class WorkerCmd(list):

    @classmethod
    def match(self, feed_item):
        """TODO: """
    
    
    
    
