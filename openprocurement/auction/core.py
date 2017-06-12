from zope.interface import implementer,Interface
from zope.interface.interface import InterfaceClass
from pkg_resources import iter_entry_points

from .components import components
from .interfaces import IFeedItem, IAuctionDatabridge,\
    IAuctionManager, IWorkerCmdFactory, IWorkerCommand,\
    IAuction, IAuctionType


PKG_NAMESPACE = "openprocurement.auction.plugins"
DEFAULT_PROCUREMENT_METHOD_TYPES = [
    'belowThreshold',
    'aboveThresholdUA',
    'aboveThresholdEU',
    'competitiveDialogueEU.stage2',
    'competitiveDialogueUA.stage2',
    'aboveThresholdUA.defense'
]


@components.adapter(
    provides=IWorkerCmdFactory, adapts=(IAuctionDatabridge, IFeedItem)
)
@implementer(IAuctionManager)
class AuctionManager(object):

    def __init__(self, databridge, feed):
        self.databridge = databridge
        self.feed_item = feed
        plugins = self.databridge.config_get('plugins') or []

        # TODO:
        for entry_point in iter_entry_points(PKG_NAMESPACE):
            if entry_point.name in plugins:
                plugin = entry_point.load()
                plugin(components)

    def __call__(self):
        auction_iface = components.q(IAuctionType, name=self.feed_item.get(
            'procurementMethodType',
            ''
        ))
        if not auction_iface:
            return
        print "Has lots {} -> {}".format(hasattr(self.feed_item, 'lots'), auction_iface)
        return components.queryMultiAdapter(
            (self.databridge, self.feed_item),
            auction_iface
        )


@implementer(IWorkerCommand)
class SimpleWorker(object):

    def __init__(self, databridge, feed_item):
        self.bridge = databridge
        self.auction_data = feed_item

    def iter_planning(self):
        if self.auction_data['status'] == "active.auction":
            if 'auctionPeriod' in self.auction_data and 'startDate' in self.auction_data['auctionPeriod'] \
               and 'endDate' not in self.auction_data['auctionPeriod']:
              
                start_date, auctions_start_in_date\
                    = self.bridge.item_auction_start_date(self.auction_data)
                if datetime.now(self.bridge.tz) > start_date:
                    # self.log('SKIP')
                    raise StopIteration
                if self.bridge.re_planning and self.auction_data['id'] in self.bridge.tenders_ids_list:
                    # self.log('ALREADY_REPLANNDED')
                    raise StopIteration
                elif not self.bridge.re_planning and [
                        row.id for row in auctions_start_in_date.rows
                        if row.id == self.auction_data['id']
                ]:
                    # self.log('ALREADY_PLANNDED')
                    raise StopIteration
                yield (str(self.auction_data['id']), )

        if self.auction_data['status'] == "cancelled":
            future_auctions = endDate_view(
                self.bridge.db, startkey=time() * 1000
            )
            if self.auction_data["id"] in [i.id for i in future_auctions]:
                self.log('SELECTED_FOR_CANCELLATION')
                LOGGER.info('celected_for_cancellation')
                # TODO:
                yield "auction cancelled"
                #bridge.start_auction_worker_cmd('cancel', item["id"])
        raise StopIteration


for _type in DEFAULT_PROCUREMENT_METHOD_TYPES:
    # TODO: lots and features
    iface = InterfaceClass(
        "{}_IAuction".format(_type),
        bases=(IAuction,)
    )
    components.registerUtility(iface, IAuctionType, name=_type)
    components.adapter(
        provides=iface,
        adapts=(IAuctionDatabridge, IFeedItem)
    )(SimpleWorker)
