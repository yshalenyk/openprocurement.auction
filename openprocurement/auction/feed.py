from munch import Munch
from zope.interface import implementer
from .interfaces import IFeedItem


@implementer(IFeedItem)
class FeedItem(Munch):
    """"""
