import logging
from systemd_msgs_ids import (
    DATA_BRIDGE_PLANNING_TENDER_SKIP,
    DATA_BRIDGE_RE_PLANNING_TENDER_ALREADY_PLANNED
)
from .intefaceses import IAuctionLogger

LOGGER = logging.getLogger(__name__)
LOGMAP = {
    "SKIP" : {
        msg: "Tender {} start date in past. Skip it for planning",
        extra: {
            'MESSAGE_ID': DATA_BRIDGE_PLANNING_TENDER_SKIP
        }
    },
    "ALREADY_REPLANNED": {
        msg: "Tender {} already planned while replanning",
        extra: {
            'MESSAGE_ID': DATA_BRIDGE_RE_PLANNING_TENDER_ALREADY_PLANNED
        }
    },
    "ALREADY_PLANNED": {
        msg: "Tender {} already planned on same date",
        extra: {
            'MESSAGE_ID': DATA_BRIDGE_PLANNING_TENDER_ALREADY_PLANNED
        }
    },
    "CANCELLED": {
        msg: 'Tender {0} selected for cancellation'
    }
}


@implementer(IAuctionLogger)
class AuctionLogger(object):
    messages = LOGMAP

    def __init__(self, logger=LOGGER, level=logging.INFO):
        self.logger = logger
        self.level = level
        self._log_func = getattr(self.logger, self.level.lower(), logger.info)

    def _with_item_id(self, item_id):


    def __get__(self, instance, owner):
        return self._with_item_id(instance.)
        
    def __set__(self, instance, value):
        self.logger = value
        
    def __call__(self, msg=""):
        if msg and msg in self.messages:
            self._log_fun(self.messages.get(msg))
        self._log_func(msg)
