import logging
import sys

from copy import deepcopy
from zope.interface import implementer
from urlparse import urljoin
from couchdb import Database, Session
from gevent.event import Event
from gevent.lock import BoundedSemaphore
from requests import Session as RequestsSession
from barbecue import calculate_coeficient

from openprocurement.auction.systemd_msgs_ids import (
    AUCTION_WORKER_API_AUCTION_RESULT_NOT_APPROVED,
    AUCTION_WORKER_API_AUCTION_CANCEL,
    AUCTION_WORKER_API_AUCTION_NOT_EXIST,
    AUCTION_WORKER_SERVICE_NUMBER_OF_BIDS
    )
from openprocurement.auction.tenders_types import multiple_lots_tenders
from openprocurement.auction.interfaces import IAuctionWorker
from openprocurement.auction.services import\
    DBServiceMixin, RequestIDServiceMixin, AuditServiceMixin,\
    DateTimeServiceMixin, BiddersServiceMixin, PostAuctionServiceMixin,\
    StagesServiceMixin, AuctionRulerMixin, ROUNDS
from openprocurement.auction.utils import get_tender_data


LOGGER = logging.getLogger('Auction Worker')


class MultilotDBServiceMixin(DBServiceMixin):

    def get_auction_info(self, prepare=False):
        if not self.debug:
            if prepare:
                self._auction_data = get_tender_data(
                    self.tender_url,
                    request_id=self.request_id,
                    session=self.session
                )
            else:
                self._auction_data = {'data': {}}
            auction_data = get_tender_data(
                self.tender_url + '/auction',
                user=self.worker_defaults['TENDERS_API_TOKEN'],
                request_id=self.request_id,
                session=self.session
            )
            if auction_data:
                self._auction_data['data'].update(auction_data['data'])
                del auction_data
            else:
                self.get_auction_document()
                if self.auction_document:
                    self.auction_document['current_stage'] = -100
                    self.save_auction_document()
                    LOGGER.warning('Cancel auction: {}'.format(
                        self.auction_doc_id
                    ), extra={'JOURNAL_REQUEST_ID': self.request_id,
                              'MESSAGE_ID': AUCTION_WORKER_API_AUCTION_CANCEL})
                else:
                    LOGGER.error('Auction {} not exists'.format(
                        self.auction_doc_id
                    ), extra={'JOURNAL_REQUEST_ID': self.request_id,
                              'MESSAGE_ID': AUCTION_WORKER_API_AUCTION_NOT_EXIST})
                self._end_auction_event.set()
                sys.exit(1)
        self._lot_data = dict({item['id']: item for item in self._auction_data['data']['lots']}[self.lot_id])
        self._lot_data['items'] = [item for item in self._auction_data['data'].get('items', [])
                                   if item.get('relatedLot') == self.lot_id]
        self._lot_data['features'] = [
            item for item in self._auction_data['data'].get('features', [])
            if item['featureOf'] == 'tenderer'
            or item['featureOf'] == 'lot' and item['relatedItem'] == self.lot_id
            or item['featureOf'] == 'item' and item['relatedItem'] in [i['id'] for i in self._lot_data['items']]
        ]
        self.startDate = self.convert_datetime(
            self._lot_data['auctionPeriod']['startDate']
        )
        self.bidders_features = None
        self.features = self._lot_data.get('features', None)
        if not prepare:
            codes = [i['code'] for i in self._lot_data['features']]
            self.bidders_data = []
            for bid_index, bid in enumerate(self._auction_data['data']['bids']):
                if bid.get('status', 'active') == 'active':
                    for lot_index, lot_bid in enumerate(bid['lotValues']):
                        if lot_bid['relatedLot'] == self.lot_id and lot_bid.get('status', 'active') == 'active':
                            bid_data = {
                                'id': bid['id'],
                                'date': lot_bid['date'],
                                'value': lot_bid['value']
                            }
                            if 'parameters' in bid:
                                bid_data['parameters'] = [i for i in bid['parameters']
                                                          if i['code'] in codes]
                            self.bidders_data.append(bid_data)
            self.bidders_count = len(self.bidders_data)
            LOGGER.info('Bidders count: {}'.format(self.bidders_count),
                        extra={'JOURNAL_REQUEST_ID': self.request_id,
                               'MESSAGE_ID': AUCTION_WORKER_SERVICE_NUMBER_OF_BIDS})
            self.rounds_stages = []
            for stage in range((self.bidders_count + 1) * ROUNDS + 1):
                if (stage + self.bidders_count) % (self.bidders_count + 1) == 0:
                    self.rounds_stages.append(stage)
            self.mapping = {}
            if self._lot_data.get('features', None):
                self.bidders_features = {}
                self.bidders_coeficient = {}
                self.features = self._lot_data['features']
                for bid in self.bidders_data:
                    self.bidders_features[bid['id']] = bid['parameters']
                    self.bidders_coeficient[bid['id']] = calculate_coeficient(self.features, bid['parameters'])
            else:
                self.bidders_features = None
                self.features = None

            for index, uid in enumerate(self.bidders_data):
                self.mapping[self.bidders_data[index]['id']] = str(index + 1)

    def prepare_auction_document(self):
        self.generate_request_id()
        public_document = self.get_auction_document()

        self.auction_document = {}
        if public_document:
            self.auction_document = {"_rev": public_document["_rev"]}
        if self.debug:
            self.auction_document['mode'] = 'test'
            self.auction_document['test_auction_data'] = deepcopy(self._auction_data)

        self.get_auction_info(prepare=True)
        if self.worker_defaults.get('sandbox_mode', False):
            submissionMethodDetails = self._auction_data['data'].get('submissionMethodDetails', '')
            if submissionMethodDetails == 'quick(mode:no-auction)':
                results = multiple_lots_tenders.post_results_data(self, with_auctions_results=False)
                return 0
            elif submissionMethodDetails == 'quick(mode:fast-forward)':
                self.auction_document = multiple_lots_tenders.prepare_auction_document(self)
                if not self.debug:
                    self.set_auction_and_participation_urls()
                self.get_auction_info()
                self.prepare_auction_stages_fast_forward()
                self.save_auction_document()
                multiple_lots_tenders.post_results_data(self, with_auctions_results=False)
                self.save_auction_document()
                return

        self.auction_document = multiple_lots_tenders.prepare_auction_document(self)

        self.save_auction_document()
        if not self.debug:
            self.set_auction_and_participation_urls()


class MultilotAuditServiceMixin(AuditServiceMixin):
    def prepare_audit(self):
        self.audit = {
            "id": self.auction_doc_id,
            "tenderId": self._auction_data["data"].get("tenderID", ""),
            "tender_id": self.tender_id,
            "timeline": {
                "auction_start": {
                    "initial_bids": []
                }
            },
            "lot_id": self.lot_id
        }
        for round_number in range(1, ROUNDS + 1):
            self.audit['timeline']['round_{}'.format(round_number)] = {}


class MultilotBiddersServiceMixin(BiddersServiceMixin):
    def set_auction_and_participation_urls(self):
        multiple_lots_tenders.prepare_auction_and_participation_urls(self)


class MultilotPostAuctionServiceMixin(PostAuctionServiceMixin):
    def put_auction_data(self):
        if self.worker_defaults.get('with_document_service', False):
            doc_id = self.upload_audit_file_with_document_service()
        else:
            doc_id = self.upload_audit_file_without_document_service()

        results = multiple_lots_tenders.post_results_data(self)

        if results:
            bids_information = None
            if doc_id and bids_information:
                self.approve_audit_info_on_announcement(approved=bids_information)
                if self.worker_defaults.get('with_document_service', False):
                    doc_id = self.upload_audit_file_with_document_service(doc_id)
                else:
                    doc_id = self.upload_audit_file_without_document_service(doc_id)

                return True
        else:
            LOGGER.info(
                "Auctions results not approved",
                extra={"JOURNAL_REQUEST_ID": self.request_id,
                       "MESSAGE_ID": AUCTION_WORKER_API_AUCTION_RESULT_NOT_APPROVED}
            )

    def post_announce(self):
        self.generate_request_id()
        self.get_auction_document()
        multiple_lots_tenders.announce_results_data(self, None)
        self.save_auction_document()



@implementer(IAuctionWorker)
class Auction(MultilotDBServiceMixin,
              RequestIDServiceMixin,
              MultilotAuditServiceMixin,
              MultilotBiddersServiceMixin,
              DateTimeServiceMixin,
              StagesServiceMixin,
              MultilotPostAuctionServiceMixin,
              AuctionRulerMixin):
    """Auction Worker Class"""

    klass = "multilot_auction"

    def __init__(self, tender_id,
                 lot_id,
                 worker_defaults={},
                 auction_data={}):
        super(Auction, self).__init__()
        self.generate_request_id()
        self.tender_id = tender_id
        self.lot_id = lot_id
        self.auction_doc_id = tender_id + "_" + lot_id
        self.tender_url = urljoin(
            worker_defaults["TENDERS_API_URL"],
            '/api/{0}/tenders/{1}'.format(
                worker_defaults["TENDERS_API_VERSION"], tender_id
            )
        )
        if auction_data:
            self.debug = True
            LOGGER.setLevel(logging.DEBUG)
            self._auction_data = auction_data
        else:
            self.debug = False
        self._end_auction_event = Event()
        self.bids_actions = BoundedSemaphore()
        self.session = RequestsSession()
        self.worker_defaults = worker_defaults
        if self.worker_defaults.get('with_document_service', False):
            self.session_ds = RequestsSession()
        self._bids_data = {}
        self.db = Database(str(self.worker_defaults["COUCH_DATABASE"]),
                           session=Session(retry_delays=range(10)))
        self.audit = {}
        self.retries = 10
        self.bidders_count = 0
        self.bidders_data = []
        self.bidders_features = {}
        self.bidders_coeficient = {}
        self.features = None
        self.mapping = {}
        self.rounds_stages = []
