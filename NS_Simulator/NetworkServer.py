from .Scheduler import *
from .Frame import Frame
from .LoRaGateway import LoRaGateway
from .EndDevice import EndDevice
# Debug macro
DEBUG = False
def debug_log(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

class NetworkServer:
    def __init__(self,scheduler):
        self.end_devices = {}  # device_id -> device_info
        self.gateways = {}     # gateway_id -> gateway_info
        self.downlink_queue = []  # (scheduled_time, device_id, packet)
        self.uplink_history = []  # (arrival_time, device_id, packet)
        self.failed_frames = []
        self.Scheduler = scheduler
        self.time_window = 0

    def init_scheduler(self):
        self.Scheduler.gateways = self.gateways
        #print(f"NetworkServer initialized with scheduler type: {self.Scheduler.type_scheduler}")
        if self.Scheduler.type_scheduler == "ARMED" or self.Scheduler.type_scheduler == "TRADITIONAL":
            # Additional initialization for ARMED type
            self.Scheduler.initialize_options()
    def register_gateway(self, gateway):
        self.gateways[gateway.gateway_id] = gateway
        self.Scheduler.next_available_time[gateway.gateway_id] = {'0': 0, '1': 0}   # Initialize next available time
        debug_log(f"Gateway registered: {gateway.gateway_id}")

    def register_end_device(self, device):
        self.end_devices[device.EndDeviceID] = device 
        debug_log(f"End device registered: {device.EndDeviceID}")

    def is_confirmed(self, frame):
        """Check if the device is confirmed."""
        debug_log("Checking if frame is confirmed:", frame[0])
        if frame[0].Ftype == 4:  # Assuming Ftype 4 indicates a confirmed uplink
            debug_log("Frame is confirmed.")
            return True
        debug_log("Frame is not confirmed.")
        return False

    def receive_uplink(self, frames, confirmed):
        # Here we handled duplicated frames so frames is actually a list of frames that where transmited at the same time
        # Determine the current 1-hour window based on the first frame's arrival time

        if self.time_window != (frames[0].receivedTime // 3600):
            self.time_window = frames[0].receivedTime // 3600
            for gw in self.gateways.values():
                gw.available_tx_time[1] = 36
                gw.available_tx_time[2] = 360
        if confirmed:
            gateway_id_selected_DL, DL_frame,failed,reference_UL = self.Scheduler.schedule_downlink(frames, self.gateways)
            debug_log(f"Scheduling downlink: Gateway {gateway_id_selected_DL}, Frame: {DL_frame}")
            if DL_frame != None:
                self.downlink_queue.append((DL_frame.sendTime, DL_frame.receiverID, DL_frame))            
                self.gateways[gateway_id_selected_DL].dl_queue_update(DL_frame)
                debug_log(f"Downlink frame added to queue: {DL_frame}")
                
            else:
                debug_log("No downlink frame scheduled due to conflicts or duty cycle limits.")
                self.failed_frames.append((frames, failed))
                debug_log("No downlink frame scheduled.")
            return DL_frame,failed,reference_UL
        return None,None,None
