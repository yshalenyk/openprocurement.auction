from gevent import monkey
monkey.patch_all()


try:
    import urllib3.contrib.pyopenssl
    urllib3.contrib.pyopenssl.inject_into_urllib3()
except ImportError:
    pass

import logging
import logging.config
import os
import argparse
import iso8601

from datetime import datetime
from time import sleep, mktime, time
from urlparse import urljoin

from apscheduler.schedulers.gevent import GeventScheduler
from gevent.queue import Queue, Empty
from gevent.subprocess import check_call

from couchdb import Database, Session
from dateutil.tz import tzlocal
from systemd_msgs_ids import (
    DATA_BRIDGE_PLANNING_START_BRIDGE,
    DATA_BRIDGE_PLANNING_DATA_SYNC,
    DATA_BRIDGE_PLANNING_TENDER_SKIP,
    DATA_BRIDGE_PLANNING_TENDER_ALREADY_PLANNED,
    DATA_BRIDGE_PLANNING_LOT_SKIP,
    DATA_BRIDGE_PLANNING_LOT_ALREADY_PLANNED,
    DATA_BRIDGE_PLANNING_SKIPED_TEST,
    DATA_BRIDGE_PLANNING_SELECT_TENDER,
    DATA_BRIDGE_PLANNING_DATA_SYNC_RESUME,
    DATA_BRIDGE_PLANNING_COUCH_FEED,
    DATA_BRIDGE_PLANNING_COUCH_DATA_SYNC,
    DATA_BRIDGE_RE_PLANNING_START_BRIDGE,
    DATA_BRIDGE_RE_PLANNING_TENDER_ALREADY_PLANNED,
    DATA_BRIDGE_RE_PLANNING_LOT_ALREADY_PLANNED,
    DATA_BRIDGE_RE_PLANNING_FINISHED
)
from openprocurement_client.sync import get_tenders
from yaml import load
from .design import endDate_view, startDate_view, PreAnnounce_view
from .utils import do_until_success
#from .log import AuctionLogger
from design import sync_design

from zope.interface import implementer
from .interfaces import IAuctionDatabridge, IWorkerCmdFactory, IFeedItem
from .components import components
from .feed import FeedItem


API_EXTRA = {'opt_fields': 'status,auctionPeriod,lots,procurementMethodType', 'mode': '_all_'}
LOGGER = logging.getLogger(__name__)


@components.component()
@implementer(IAuctionDatabridge)
class AuctionsDataBridge(object):

    """Auctions Data Bridge"""
    #logger = AuctionLogger(logger=LOGGER)
    logger = LOGGER

    def __init__(self, config, re_planning=False):
        super(AuctionsDataBridge, self).__init__()
        self.config = config
        self.tenders_ids_list = []
        self.tz = tzlocal()

        self.couch_url = urljoin(
            self.config_get('couch_url'),
            self.config_get('auctions_db')
        )
        self.db = Database(self.couch_url,
                           session=Session(retry_delays=range(10)))
        sync_design(self.db)
        self.re_planning = re_planning

    def config_get(self, name):
        return self.config.get('main').get(name)

    def run(self):
        if self.re_planning:
            self.run_re_planning()
            return
        self.logger.info('Start Auctions Bridge',
                    extra={'MESSAGE_ID': DATA_BRIDGE_PLANNING_START_BRIDGE})
        self.logger.info('Start data sync...',
                    extra={'MESSAGE_ID': DATA_BRIDGE_PLANNING_DATA_SYNC})

        for feed in get_tenders(host=self.config_get('tenders_api_server'),
                                version=self.config_get('tenders_api_version'),
                                key='', extra_params=API_EXTRA):
            # magic should happen here
            # TODO:
            item = FeedItem(feed)
            factory = components.queryMultiAdapter(
                (self, item),
                IWorkerCmdFactory
            )
            factory = factory and factory()
            if factory:
                for cmd in factory():
                    # TODO: better cmd
                    # TODO: better logging
                    # self.logger.info('Tender {0} selected for planning'.format(*planning_data))
                    # self.run_worker(cmd)
                    print cmd

    def run_worker(self, params):
        params = [self.config_get('auction_worker'),
                  params,
                  self.config_get('auction_worker_config')]
        result = do_until_success(
            check_call,
            args=(params,),
        )

        self.logger.info("Auction command {} result: {}".format(params[1], result))

    def run_re_planning(self):
        pass
        # self.re_planning = True
        # self.offset = ''
        # logger.info('Start Auctions Bridge for re-planning...',
        #             extra={'MESSAGE_ID': DATA_BRIDGE_RE_PLANNING_START_BRIDGE})
        # for tender_item in self.get_teders_list(re_planning=True):
        #     logger.debug('Tender {} selected for re-planning'.format(tender_item))
        #     for planning_data in self.get_teders_list():
        #         if len(planning_data) == 1:
        #             logger.info('Tender {0} selected for planning'.format(*planning_data))
        #             self.start_auction_worker_cmd('planning', planning_data[0])
        #         elif len(planning_data) == 2:
        #             logger.info('Lot {1} of tender {0} selected for planning'.format(*planning_data))
        #             self.start_auction_worker_cmd('planning', planning_data[0], lot_id=planning_data[1])
        #         self.tenders_ids_list.append(tender_item['id'])
        #     sleep(1)
        # logger.info("Re-planning auctions finished",
        #             extra={'MESSAGE_ID': DATA_BRIDGE_RE_PLANNING_FINISHED})


def main():
    parser = argparse.ArgumentParser(description='---- Auctions Bridge ----')
    parser.add_argument('config', type=str, help='Path to configuration file')
    parser.add_argument(
        '--re-planning', action='store_true', default=False,
        help='Not ignore auctions which already scheduled')
    params = parser.parse_args()
    if os.path.isfile(params.config):
        with open(params.config) as config_file_obj:
            config = load(config_file_obj.read())
        logging.config.dictConfig(config)
        bridge = AuctionsDataBridge(config, re_planning=args.re_plannging)
        bridge.run()

if __name__ == "__main__":
    main()
