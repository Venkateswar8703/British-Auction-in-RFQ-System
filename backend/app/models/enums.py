import enum


class UserRole(str, enum.Enum):
    BUYER = "buyer"
    SUPPLIER = "supplier"


class RFQStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    FORCE_CLOSED = "FORCE_CLOSED"


class TriggerType(str, enum.Enum):
    BID_RECEIVED = "BID_RECEIVED"
    ANY_RANK_CHANGE = "ANY_RANK_CHANGE"
    L1_CHANGE = "L1_CHANGE"


class InvitationStatus(str, enum.Enum):
    INVITED = "INVITED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"


class AuctionEventType(str, enum.Enum):
    BID_SUBMITTED = "BID_SUBMITTED"
    RANK_CHANGED = "RANK_CHANGED"
    L1_CHANGED = "L1_CHANGED"
    EXTENSION_APPLIED = "EXTENSION_APPLIED"
    EXTENSION_CAPPED = "EXTENSION_CAPPED"
    AUCTION_STARTED = "AUCTION_STARTED"
    AUCTION_CLOSED = "AUCTION_CLOSED"
    FORCED_CLOSE = "FORCED_CLOSE"

