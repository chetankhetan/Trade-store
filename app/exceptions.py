class TradeError(Exception):
    """Base exception class for all trade-related business logic errors."""
    status_code = 400

class VersionError(TradeError):
    def __init__(self, incoming: int, existing: int): 
        self.incoming = incoming
        self.existing = existing
        # Explicit status_code override if needed, or defaults to 400 from base class
        self.status_code = 400  
        super().__init__(f"Incoming version {incoming} is lower than existing {existing}")

class MaturityError(TradeError):
    def __init__(self, message: str = "Maturity date is before today"):
        self.status_code = 400
        super().__init__(message)
