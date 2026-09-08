import os
from ..Schedulers import Scheduler
import math
import numpy as np
import random
DEBUG = False
EPOCHS = 20
LOAD = 20  # Number of packets to simulate
MOMENTS = 100
np.set_printoptions(suppress=True, precision=8)
class Config:
    def __init__(self,debug_file):
        self.file_name = debug_file

    def debug_log(self, *args, **kwargs):
        if DEBUG:
            print(*args, **kwargs)
            with open(self.file_name, "a") as f:
                print(*args, **kwargs, file=f)

class DutyCyleControl(Scheduler.Scheduler):
    def __init__(self,type_scheduler, resources,duty_cycle="blocked", consider_all_gw=True, debug_file="debug_log.txt", dc_envelope="linear", dc_exponential_k=1.0):
        super().__init__(type_scheduler,consider_all_gw)
        self.debug = Config(debug_file)
        self.schedule = {}
        self.debug.debug_log("DutyCyleControl scheduler initialized successfully!")
        self.duty_cycle_cons_rate = {}
        self.resources = resources
        self.duty_cycle = duty_cycle  # Can be "blocked" or "budget"
        self.next_available_time = {}
        self.total_counts = 0  # Total number of trials for bandit algorithm
        self.available_options = []  # Store available options for each gateway
        self.gateway_inter_time = {}
        self.DutyCycle_window = 3600  # 1 hour window for duty cycle calculation
        self.count = 0
        self.linear_dc_state = {}
        self.dc_envelope = dc_envelope
        self.dc_exponential_k = dc_exponential_k
        
         

        # ADD THIS LINE:
        self.recent_scheduling_times = {}  # Track scheduling times for load calculation
        # ADD THIS LINE:
        self.recent_scheduling_times = {}  # Track scheduling times for load calculation
        if os.path.exists(self.debug.file_name):
            os.remove(self.debug.file_name)

    def _get_rx_budget_seconds(self, rx):
        return 36 if rx == 0 else 360

    def _envelope_fraction(self, progress):
        """Map normalized progress in [0,1] to allowed budget fraction.

        Modes:
          linear      : phi(x) = x                            (uniform spread)
          cubic       : phi(x) = x^3                          (conservative early)
          exponential : phi(x) = (e^kx - 1) / (e^k - 1)      (tunable, conservative early)
          logarithmic : phi(x) = ln(1+kx) / ln(1+k)          (front-loaded, generous early)
        """
        progress = min(max(progress, 0.0), 1.0)
        mode = str(self.dc_envelope).lower()

        if mode == "cubic":
            return progress ** 3

        if mode == "exponential":
            k = max(float(self.dc_exponential_k), 1e-9)
            den = math.exp(k) - 1.0
            if den <= 0:
                return progress
            return (math.exp(k * progress) - 1.0) / den

        if mode == "logarithmic":
            k = max(float(self.dc_exponential_k), 1e-9)
            den = math.log(1.0 + k)
            if den <= 0:
                return progress
            return math.log(1.0 + k * progress) / den

        # Default: linear pacing.
        return progress

    def _get_linear_headroom(self, gw, rx, current_time):
        """Return allowed extra ToA under the configured pacing envelope."""
        key = (gw, rx)
        if key not in self.linear_dc_state:
            self.linear_dc_state[key] = {
                "window_start": current_time,
                "used_toa": 0.0,
            }

        state = self.linear_dc_state[key]
        window_start = state["window_start"]

        if current_time - window_start >= self.DutyCycle_window:
            windows_passed = int((current_time - window_start) // self.DutyCycle_window)
            state["window_start"] = window_start + windows_passed * self.DutyCycle_window
            state["used_toa"] = 0.0

        elapsed = max(0.0, current_time - state["window_start"])
        budget = self._get_rx_budget_seconds(rx)
        progress = min(elapsed / self.DutyCycle_window, 1.0)
        allowed_used = budget * self._envelope_fraction(progress)
        headroom = allowed_used - state["used_toa"]
        return headroom, allowed_used, state["used_toa"]

    def _consume_linear_budget(self, gw, rx, toa):
        key = (gw, rx)
        if key in self.linear_dc_state:
            self.linear_dc_state[key]["used_toa"] += max(0.0, toa)

    def initialize_options(self):
        self.debug.debug_log("Initializing options for gateways")
        for gw in self.gateways:
            for rx in range(2):  # Assuming 2 Rx windows
                self.acumualted_blocked[(gw, rx)] = 0   
                self.duty_cycle_cons_rate[(gw, rx)] = []
                self.duty_cycle_cons_rate[(gw, rx)].append(36 if rx ==0 else 360)  # Initial duty cycle budget
            self.gateway_inter_time[gw] = []




   

   
   



    def schedule_downlink(self, frames, gateways):

        


        sendTime = frames[0].sendTime
        self.debug.debug_log("Frame transmited at: ", frames[0].sendTime)


        gw_received_UL = [] #tuple of gateway that received the uplink frame (which is the same)
        sender = frames[0].senderId
        received_gws = []
        final_options = {}
        failed = []
        self.count +=1
       
        ul_gateways = [(frame.receiverID, frame.senderId, frame.SNR, frame) for frame in frames]
        ul_gateways.sort(key=lambda x: x[2], reverse=True)
        change_dc = {}
        for frame_set in ul_gateways:
            self.gateway_inter_time[frame_set[0]].append(frame_set[3].receivedTime)

            gw_received_UL.append((frame_set[0],frame_set[2]))
            received_gws.append(frame_set[0])
            frame = None
            for rx in range(2): 
                frame = self.DownlinkFrame(sender, frame_set[0], frames[0], rx)

                ToA = frame.receivedTime - frame.sendTime
                final_options[(frame_set[0],rx)] = frame
                headroom, allowed_used, used_toa = self._get_linear_headroom(frame_set[0], rx, frames[0].sendTime)
                projected_slack = headroom - ToA
                change_dc[(frame_set[0],rx)] = projected_slack
                #print(f"Gateway {frame_set[0]} Rx {rx} - ToA: {ToA}, Available Time: {available_time}, Change DC: {change_dc[(frame_set[0],rx)]}")
                    


                
         # Update trials for selected gateway
        gw_snr = [gw for gw,_,_,_ in ul_gateways]
        #actions = self.select_option(change_dc,frames[0].SF)
        selected_options = {}
        # Sort by projected slack (smaller positive slack means closer to the target linear envelope)
        change_dc = dict(sorted(change_dc.items(), key=lambda x: x[1]))
        for action in change_dc:
            rx = action[1]
            ToA = final_options[(action[0],action[1])].receivedTime - final_options[(action[0],action[1])].sendTime
            headroom, allowed_used, used_toa = self._get_linear_headroom(action[0], action[1], frames[0].sendTime)
            self.debug.debug_log(
                f"Evaluating option GW {action[0]} RX{action[1]+1} - "
                f"LinearHeadroom: {headroom:.3f}s, ToA: {ToA:.2f}s, "
                f"AllowedUsed: {allowed_used:.3f}s, Used: {used_toa:.3f}s"
            )
            if ToA <= headroom + 1e-9:  # Enforce linear duty-cycle pacing envelope
                selected_options[(action[0],action[1])] = final_options[(action[0],action[1])]



        # Define probability of prioritizing rx=1 (adjust as needed)
        prioritize_rx1_prob = 1  # 10% chance to prioritize rx=1
        
        # Randomly decide the order of rx windows
        if random.random() > prioritize_rx1_prob:
            rx_order = [1, 0]  # Prioritize rx=1
        else:
            rx_order = [0, 1]  # Keep original order
        for chosen_rx in rx_order:

            for chosen_gw_id in gw_snr:
                if (chosen_gw_id, chosen_rx) in selected_options:
                    chosen_dl_frame = selected_options[(chosen_gw_id, chosen_rx)]
                    conflict = self.check_conflicts(chosen_dl_frame, gateways[chosen_gw_id]) 
                    if not conflict:
                        if self.duty_cycle == "blocked":
                            blocked = self.check_duty_cycle(chosen_dl_frame, gateways[chosen_gw_id], chosen_dl_frame.rx_window-1,False)
                        else:
                            blocked = self.check_duty_cycle_budget(chosen_dl_frame, gateways[chosen_gw_id], chosen_dl_frame.rx_window-1,False)
                        if blocked:
                            gateways[chosen_gw_id].dl_queue_update(chosen_dl_frame)
                            self.schedule[chosen_gw_id] = chosen_dl_frame
                            toa = chosen_dl_frame.receivedTime - chosen_dl_frame.sendTime
                            self._consume_linear_budget(chosen_gw_id, chosen_rx, toa)
                            self.debug.debug_log(f"Scheduled DL frame for ED {sender} via GW {chosen_gw_id} in RX{chosen_rx+1}: ToA={chosen_dl_frame.receivedTime - chosen_dl_frame.sendTime:.2f}s")
                            for gw in self.gateways:
                                for rx in range(2):
                                    self.debug.debug_log(f"GW {gw} RX{rx+1} - Available TX Time: {self.gateways[gw].available_tx_time[rx + 1]:.2f}s")
                            self.duty_cycle_cons_rate[(chosen_gw_id, chosen_rx)].append(self.gateways[chosen_gw_id].available_tx_time[chosen_rx + 1])
                            return chosen_gw_id, chosen_dl_frame, None, frames[0]
       

        #print("No available options to schedule downlink.")            

        return None, None, failed, None

 
