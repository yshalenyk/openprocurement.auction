import pkg_resources
import logging

LOGGER = logging.getLogger('openprocurement.auction.databridge')
DEFAULT_PROCUREMENT_METHOD_TYPES = [
    'belowThreshold',
    'aboveThresholdUA',
    'aboveThresholdEU',
    'competitiveDialogueEU.stage2',
    'competitiveDialogueUA.stage2',
    'aboveThresholdUA.defense'
]


class AuctionManager(object):
    registry = {}

    @classmethod
    def register_auction_type(klass, cls):
        name = getattr(cls, 'name', False)
        if name:
            AuctionManager.registry[cls.name.lower()] = cls

    @classmethod
    def lookup(cls, item):
        reg = cls.registry
        for name in sorted(reg,
                           key=lambda x: len(reg[x].predicates), reverse=True):
            if cls.registry[name].match(item):
                return cls.registry[name]



class AuctionMeta(type):
    def __init__(cls, cname, cbases, cdict):
        AuctionManager.register_auction_type(cls)
        for klass in cls.__subclasses__():
            AuctionManager.register_auction_type(klass)
            
        return super(AuctionMeta, cls).__init__(cname, cbases, cdict)


class Auction(object):
    __metaclass__ = AuctionMeta

    @classmethod
    def match(cls, feed_item):
        return all(p(feed_item) for p in getattr(cls, 'predicates', []))


class Loader(object):
    def __init__(self, namespace, config=None):
        self.pkg_namespace = namespace
        self.config = config or {}

    def scan(self):
        LOGGER.warn("Scanning for plugins")
        for plugin in pkg_resources.iter_entry_points(self.pkg_namespace):
            LOGGER.info("Found {}".format(plugin.name))
            if not self.config or (self.config and plugin.name in self.config['plugins']):
                LOGGER.info("Loading {}".format(plugin.name))
                mixin = plugin.load()

                # create class (will be registered in manager)
                type(plugin.name.capitalize(), (Auction, mixin), {
                    'name': plugin.name,
                })

