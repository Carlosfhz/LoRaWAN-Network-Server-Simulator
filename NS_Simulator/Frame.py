class Frame:
    def __init__(self, senderId, receiverID, sendTime, receivedTime, SF, SNR, RSSI, Ftype, fcnt, rx_or_tx='tx',rx_window=None,original_SF=None,power=14):
        self.senderId = senderId
        self.receiverID = receiverID
        self.sendTime = sendTime
        self.receivedTime = receivedTime
        self.original_SF = original_SF # In the case of the downlinks for class A it correspond to the SF of the reference UL
        self.SF = SF
        self.SNR = SNR
        self.RSSI = RSSI
        self.Ftype = Ftype
        self.fcnt = fcnt
        self.power = power
        self.rx_window = rx_window
        
        self.rx_or_tx = rx_or_tx
    def __str__(self):
        return f"Frame(senderId={self.senderId}, receiverID={self.receiverID}, Ftype={self.Ftype}, SF={self.SF}, SNR={self.SNR}, RSSI={self.RSSI}, rx_or_tx={self.rx_or_tx}, receivedTime={self.receivedTime})"