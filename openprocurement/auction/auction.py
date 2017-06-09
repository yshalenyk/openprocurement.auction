import logging
import iso8601
from datetime import datetime
from time import time, mktime

from .design import endDate_view, PreAnnounce_view, startDate_view
from .core import DEFAULT_PROCUREMENT_METHOD_TYPES

from .systemd_msgs_ids import (
    DATA_BRIDGE_PLANNING_TENDER_SKIP as SKIP,
    DATA_BRIDGE_RE_PLANNING_TENDER_ALREADY_PLANNED as ALREADY_REPLANNED,
    DATA_BRIDGE_PLANNING_TENDER_ALREADY_PLANNED as ALREADY_PLANNED,
)


LOGGER = logging.getLogger(__name__)
MSG = {
    
}

class AuctionLogger(object):
    def __init__(self, level='info'):
        self.logger = logging.getLogger(__name__)
        self._log_func = getattr(self.logger, level, self.logger.info)
        self._msgs = {
            'SKIP': {
                'msg': "Tender {} start date in past. Skip it for planning",
                'extra': {'MESSAGE_ID': SKIP}
            },
            'ALREADY_REPLANNDED': {
                'msg': "Tender {} already planned while replanning",
                'extra': {'MESSAGE_ID': ALREADY_REPLANNED}
            },
            'ALREADY_PLANNDED': {
                'msg':"Tender {} already planned on same date",
                'extra':{'MESSAGE_ID': ALREADY_PLANNED}
            },
            'SELECTED_FOR_CANCELLATION': {
                'msg':'Tender {} selected for cancellation',
            }
        } 

    def __set__(self, instance, value):
        self.logger = logger

    def __get__(self, instance, owner):
        """"""
        LOGGER.info(instance.tender_id)
        raise
        return self._log_message(instance.tender_id)

    def _log_message(self, tender_id):
        def _log(_type='', message=None):
            msg = self._msgs.get(_type)
            if msg:
                msg['msg'].format(tender_id)
                self._log_func(**msg)
                return
            if message:
                self._log_func(message)
        return _log


class Auction(object):
    name = 'SimpleAuction'
    ROUNDS = 3
    log = AuctionLogger()
    predicates = [
        lambda item: not hasattr(item, 'lots'),
        lambda item: item.get('procurementMethodType') in DEFAULT_PROCUREMENT_METHOD_TYPES,
    ]

    def __str__(self):
        return "<Simple auction object id={}>".format(self.auction_id)

    __repr__ = __str__

    def __init__(self, bridge, data):
        self.auction_data = data
        self.bridge = bridge
        self.tender_id = data.get('id')
        self.auction_id = data.get('id')
        self.log('SKIP')
        #LOGGER.info('Got document id={} status {}'.format(data['id'], data['status']))
        # TODO: Rewrite as callables
       

    def worker_cmd():
        """TODO: """

    def prepare_audit(self, raw_data={}):
        if not raw_data:
            raw_data = {
                "id": self.auction_doc_id,
                "tenderId": self._auction_data["data"].get("tenderID", ""),
                "tender_id": self.tender_id,
                "timeline": {
                    "auction_start": {
                        "initial_bids": []
                    }
                }
            }       


    def iter_planning(self, item=None):
        if self.auction_data['status'] == "active.auction":
            if 'auctionPeriod' in self.auction_data and 'startDate' in self.auction_data['auctionPeriod'] \
                and 'endDate' not in self.auction_data['auctionPeriod']:
                    
                start_date, auctions_start_in_date\
                    = self.bridge.item_auction_start_date(self.auction_data)
                if datetime.now(self.bridge.tz) > start_date:
                    self.log('SKIP')
                    raise StopIteration
                if self.bridge.re_planning and self.auction_data['id'] in self.bridge.tenders_ids_list:
                    self.log('ALREADY_REPLANNDED')
                    raise StopIteration
                elif not self.bridge.re_planning and [
                        row.id for row in auctions_start_in_date.rows
                        if row.id == self.auction_data['id']
                ]:
                    self.log('ALREADY_PLANNDED')
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
