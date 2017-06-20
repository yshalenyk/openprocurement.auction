# -*- coding: utf-8 -*-
from gevent import monkey
monkey.patch_all()

import argparse
import logging.config
import json
import sys
import os
import re

from openprocurement.auction.interfaces import IAuctionWorker
from openprocurement.auction.components import components
from openprocurement.auction.services import SCHEDULER
from openprocurement.auction.interfaces import IAuctionCli


LOGGER = logging.getLogger('Auction Worker')


def main():
    parser = components.q(IAuctionCli)
    args = parser.parse_args()

    if os.path.isfile(args.auction_worker_config):
        worker_defaults = json.load(open(args.auction_worker_config))
        if args.with_api_version:
            worker_defaults['TENDERS_API_VERSION'] = args.with_api_version
        if args.cmd != 'cleanup':
            worker_defaults['handlers']['journal']['TENDER_ID'] = args.auction_doc_id
        for key in ('TENDERS_API_VERSION', 'TENDERS_API_URL',):
            worker_defaults['handlers']['journal'][key] = worker_defaults[key]

        logging.config.dictConfig(worker_defaults)
    else:
        print "Auction worker defaults config not exists!!!"
        sys.exit(1)

    if args.auction_info_from_db:
        auction_data = {'mode': 'test'}
    elif args.auction_info:
        auction_data = json.load(open(args.auction_info))
    else:
        auction_data = None

    auction_class = components.q(IAuctionWorker, name=args.type)
    if not auction_class:
        LOGGER.warn("No registered workers with name {}".format(args.type))
        return
    auction = auction_class(args.auction_doc_id,
                            worker_defaults=worker_defaults,
                            auction_data=auction_data,
                            )
    if args.cmd == 'run':
        SCHEDULER.start()
        auction.schedule_auction()
        auction.wait_to_end()
        SCHEDULER.shutdown()
    elif args.cmd == 'planning':
        auction.prepare_auction_document()
    elif args.cmd == 'announce':
        auction.post_announce()
    elif args.cmd == 'cancel':
        auction.cancel_auction()
    elif args.cmd == 'reschedule':
        auction.reschedule_auction()


if __name__ == "__main__":
    main()
