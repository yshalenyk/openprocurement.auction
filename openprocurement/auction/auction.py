import logging
import iso8601
from datetime import datetime
from time import time, mktime

from walkabout import PredicateDomain
from zope.interface import implementer

from openprocurement.auction.design import endDate_view, startDate_view
from openprocurement.auction.interfaces import ISimpleAuction


LOGGER = logging.getLogger(__name__)

#@implementer(ISimpleAuction)
class Auction(object):

    def __init__(self, databridge, feed_item):
        self.databridge = databridge
        self.feed_item = feed_item

    def item_start_date(self, item={}):
        if not item:
            item = self.feed_item
        start_date = iso8601.parse_date(item['auctionPeriod']['startDate'])
        start_date = start_date.astimezone(self.databridge.tz)
        auctions_start_in_date = startDate_view(
            self.databridge.db,
            key=(mktime(start_date.timetuple()) + start_date.microsecond / 1E6) * 1000
        )
        return start_date, auctions_start_in_date

    def __iter__(self):
        if self.feed_item['status'] == "active.auction":
            if 'auctionPeriod' in self.feed_item and 'startDate' in self.feed_item['auctionPeriod'] \
               and 'endDate' not in self.feed_item['auctionPeriod']:
              
                start_date, auctions_start_in_date\
                    = self.item_start_date()
                if datetime.now(self.databridge.tz) > start_date:
                    # self.log('SKIP')
                    raise StopIteration
                if self.databridge.re_planning and self.feed_item['id']\
                   in self.databridge.tenders_ids_list:
                    # self.log('ALREADY_REPLANNDED')
                    raise StopIteration
                elif not self.databridge.re_planning and [
                    row.id for row in auctions_start_in_date.rows
                    if row.id == self.feed_item['id']
                ]:
                    # self.log('ALREADY_PLANNDED')
                    raise StopIteration
                yield (str(self.feed_item['id']), )
            raise StopIteration

        if self.feed_item['status'] == "cancelled":
            future_auctions = endDate_view(
                self.databridge.db, startkey=time() * 1000
            )
            if self.feed_item["id"] in [i.id for i in future_auctions]:
                # self.log('SELECTED_FOR_CANCELLATION')
                LOGGER.info('celected_for_cancellation')
                # TODO:
                yield "auction cancelled"
                #databridge.start_auction_worker_cmd('cancel', item["id"])
        raise StopIteration
    iter = __iter__

    def __call__(self):
        LOGGER.fatal("Called simple auction type={} lots={}".format(self.feed_item.get('procurementMethodType'), self.feed_item.get('lots')))
        return iter(self)
