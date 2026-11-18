from typing import Optional, Dict, Any


class MeridianException(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AuctionNotStartedError(MeridianException):
    def __init__(self, message: str = "Auction has not started yet"):
        super().__init__(code="AUCTION_NOT_STARTED", message=message, status_code=400)


class BidAfterCloseError(MeridianException):
    def __init__(self, message: str = "Bidding has concluded for this auction"):
        super().__init__(code="BID_AFTER_CLOSE", message=message, status_code=400)


class BidAfterForcedCloseError(MeridianException):
    def __init__(self, message: str = "Auction has reached forced close deadline"):
        super().__init__(code="BID_AFTER_FORCED_CLOSE", message=message, status_code=400)


class AuctionClosedError(MeridianException):
    def __init__(self, message: str = "Auction is closed"):
        super().__init__(code="AUCTION_CLOSED", message=message, status_code=400)


class SupplierNotInvitedError(MeridianException):
    def __init__(self, message: str = "Supplier is not invited to participate in this RFQ"):
        super().__init__(code="SUPPLIER_NOT_INVITED", message=message, status_code=403)


class BidNotLowerError(MeridianException):
    def __init__(self, message: str = "New bid must have a strictly lower total than your previous bid"):
        super().__init__(code="BID_NOT_LOWER", message=message, status_code=400)


class InvalidValidityDateError(MeridianException):
    def __init__(self, message: str = "Quote validity date must be on or after the pickup date"):
        super().__init__(code="INVALID_VALIDITY_DATE", message=message, status_code=400)


class RFQNotFoundError(MeridianException):
    def __init__(self, message: str = "RFQ not found"):
        super().__init__(code="RFQ_NOT_FOUND", message=message, status_code=404)


class RFQLockedError(MeridianException):
    def __init__(self, message: str = "RFQ cannot be modified once auction has started or closed"):
        super().__init__(code="RFQ_LOCKED", message=message, status_code=400)

