class LoRaGateway:
    def __init__(self, gateway_id, channel, location):
        self.gateway_id = gateway_id
        self.available_tx_time = {1: 36, 2: 360}
        self.last_transmited = None
        self.location = location
        self.dl_queue = []  # {end_device_id: [downlink_messages]}
        self.channel = channel  # Assign the channel information
        


    def dl_queue_update(self, downlink_message):
        """Add a downlink message to the queue for a specific end device."""
        self.last_transmited = (downlink_message.sendTime, downlink_message.receivedTime)
        self.dl_queue.append(downlink_message)
        #timeOnAr = downlink_message.receivedTime - downlink_message.sendTime
        #if downlink_message.rx_window == 1:
            #self.available_tx_time_Rx1 -= timeOnAr
        #elif downlink_message.rx_window == 2:
            #self.available_tx_time_Rx2 -= timeOnAr
        #else:
            #raise ValueError("Invalid Rx_Window value. Must be 1 or 2.")
    def reset_dc(self):
        """Reset the available transmission time for both RX windows."""
        self.available_tx_time = {1: 36, 2: 360}
    def check_transmiting_gateway(self, UL_frame):
        """Check if the gateway is currently transmitting."""
        if self.last_transmited is None:
            return False
        # Check if the last transmitted frame overlaps with the uplink frame
        return not (self.last_transmited[1] <= UL_frame.sendTime or self.last_transmited[0] >= UL_frame.receivedTime)
    def __str__(self):
        return (f"LoRaGateway(gateway_id={self.gateway_id}, "
                f"available_tx_time_Rx1={self.available_tx_time[1]}, "
                f"available_tx_time_Rx2={self.available_tx_time[2]}, "
                f"dl_queue_length={len(self.dl_queue)})")