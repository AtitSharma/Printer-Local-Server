from enum import Enum


class PrinterType(str, Enum):
    KOT = "KOT"
    BAR = "BAR"
    RECEIPT = "RECEIPT"


class PrinterConnectionType(str, Enum):
    USB = "USB"
    NETWORK = "NETWORK"


class PrinterDeviceType(str, Enum):
    POS = "POS"
    THERMAL = "THERMAL"