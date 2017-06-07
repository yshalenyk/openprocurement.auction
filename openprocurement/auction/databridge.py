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

from munch import Munch

from couchdb import Database, Session
from dateutil.tz import tzlocal
from systemd_msgs_ids import (
    DATA_BRIDGE_PLANNING_START_BRIDGE,
    DATA_BRIDGE_PLANNING_DATA_SYNC,
    DATA_BRIDGE_PLANNING_TENDER_SKIP,
    DATA_BRIDGE_PLANNING_TENDER_ALREADY_PLANNED,
    DATA_BRIDGE_PLANNING_SKIPED_TEST,
    DATA_BRIDGE_PLANNING_SELECT_TENDER,
    DATA_BRIDGE_PLANNING_DATA_SYNC_RESUME,
    DATA_BRIDGE_PLANNING_COUCH_FEED,
    DATA_BRIDGE_PLANNING_COUCH_DATA_SYNC,
    DATA_BRIDGE_RE_PLANNING_START_BRIDGE,
    DATA_BRIDGE_RE_PLANNING_TENDER_ALREADY_PLANNED,
    DATA_BRIDGE_RE_PLANNING_FINISHED
)
from openprocurement_client.sync import get_tenders
from .core import Loader, AuctionManager
from yaml import load
from .design import endDate_view, startDate_view, PreAnnounce_view
from .utils import do_until_success
from design import sync_design


LOGGER = logging.getLogger(__name__)
PKG_NAMESPACE = 'openprocurement.auction.plugins'


class AuctionsDataBridge(object):
    """Auctions Data Bridge"""

    def __init__(self, config, re_planning=False):
        #super(AuctionsDataBridge, self).__init__()

        self.config = config
        self.tenders_ids_list = []
        self.tz = tzlocal()
        self.re_planning = re_planning

        self.couch_url = urljoin(
            self.config_get('couch_url'),
            self.config_get('auctions_db')
        )
        self.db = Database(self.couch_url,
                           session=Session(retry_delays=range(10)))
        sync_design(self.db)

        # plugins should be specified in config file
        # in section `plugins`
        loader = Loader(PKG_NAMESPACE, self.config)
        loader.scan()
        
    def item_auction_start_date(self, item):
        start_date = iso8601.parse_date(item['auctionPeriod']['startDate'])
        start_date = start_date.astimezone(self.tz)
        return start_date, startDate_view(
            self.db,
            key=(mktime(start_date.timetuple()) + start_date.microsecond / 1E6) * 1000
        )

    def config_get(self, name):
        return self.config.get('main').get(name)

    def get_teders_list(self):
        for item in get_tenders(host=self.config_get('tenders_api_server'),
                                version=self.config_get('tenders_api_version'),
                                key='', extra_params={'opt_fields': 'status,auctionPeriod,lots,procurementMethodType', 'mode': '_all_'}):
            cls = AuctionManager.lookup(item)
            if cls:
                auction = cls(self, item)
                for data in auction.iter_planning():
                    if data:
                        yield auction.generate_worker_cmd()

    def start_auction_worker_cmd(self, cmd):
        # TODO: fix me
        actual = cmd(self.config)
        #params = [self.config_get('auction_worker'),
        #          cmd, tender_id,
        #          self.config_get('auction_worker_config')]
        result = do_until_success(
            check_call,
            args=(actual,),
        )

        LOGGER.info("Auction command {} result: {}".format(actual, result))

    def run(self):
        if self.re_planning:
            self.run_re_planning()
            return
        LOGGER.info('Start Auctions Bridge',
                    extra={'MESSAGE_ID': DATA_BRIDGE_PLANNING_START_BRIDGE})
        LOGGER.info('Start data sync...',
                    extra={'MESSAGE_ID': DATA_BRIDGE_PLANNING_DATA_SYNC})
        for cmd_gen in self.get_teders_list():
            # TODO: fix logging. Hook??
            # LOGGER.info('Tender {0} selected for planning'.format(*planning_data))
            # LOGGER.info('Lot {1} of tender {0} selected for planning'.format(*planning_data))
            self.start_auction_worker_cmd(cmd_gen)
            # if len(planning_data) == 1:
            #     self.start_auction_worker_cmd('planning', planning_data[0])
            # elif len(planning_data) == 2:
            #     self.start_auction_worker_cmd('planning', planning_data[0], lot_id=planning_data[1])

    def run_re_planning(self):
        # TODO:
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
        bridge = AuctionsDataBridge(config, params.re_planning)
        bridge.run()


if __name__ == "__main__":
    main()
