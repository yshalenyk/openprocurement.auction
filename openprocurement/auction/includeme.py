from zope.interface.interface import InterfaceClass
from zope.interface import implementer

from openprocurement.auction.auction import Auction
from openprocurement.auction.constants import DEFAULT_PROCUREMENT_METHOD_TYPES
from openprocurement.auction.predicates import ProcurementMethodType
from openprocurement.auction.interfaces import IAuction, IFeedItem, IAuctionDatabridge


def includeme(components):

    components.add_predicate(
        'procurementMethodType',
        ProcurementMethodType
    )

    for procurement_method_type in DEFAULT_PROCUREMENT_METHOD_TYPES:
        iface = InterfaceClass(
            "{}_ISimpleAuction".format(procurement_method_type),
            bases=(IAuction,)
        )
        components.add_auction(
            iface,
            procurementMethodType=procurement_method_type
        )
        components.registerAdapter(
            implementer(iface)(Auction),
            (IAuctionDatabridge, IFeedItem),
            iface
        )
        # TODO:
        # component.add_worker(auction_iface, worker)

    
