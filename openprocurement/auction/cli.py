import argparse
from zope.interface import implementer
from openprocurement.auction.interfaces import IAuctionCli


@implementer(IAuctionCli)
class AuctionCliParse(argparse.ArgumentParser):
    """ Openprocurement Auction worker argumet parser """


PLANNING_FULL = "full"
PLANNING_PARTIAL_DB = "partial_db"
PLANNING_PARTIAL_CRON = "partial_cron"

parser = argparse.ArgumentParser(description='---- Auction ----')

parser.add_argument('cmd', type=str, help='')
parser.add_argument('auction_doc_id', type=str, help='auction_doc_id')
parser.add_argument('auction_worker_config', type=str,
                    help='Auction Worker Configuration File')
parser.add_argument('--auction_info', type=str, help='Auction File')
parser.add_argument('--type', type=str, default='default', help='Auction Type')
parser.add_argument('--auction_info_from_db', type=str, help='Get auction data from local database')
parser.add_argument('--with_api_version', type=str, help='Tender Api Version')
parser.add_argument('--planning_procerude', type=str, help='Override planning procerude',
                        default=None, choices=[None, PLANNING_FULL, PLANNING_PARTIAL_DB, PLANNING_PARTIAL_CRON])


