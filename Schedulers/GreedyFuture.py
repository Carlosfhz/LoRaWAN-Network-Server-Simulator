import os
from NS_Simulator import Scheduler
import math
import numpy as np
DEBUG = False

EPOCHS = 20
np.set_printoptions(suppress=True, precision=8)
class Config:
    def __init__(self,debug_file):
        self.file_name = debug_file

    def debug_log(self, *args, **kwargs):
        if DEBUG:
            print(*args, **kwargs)
            with open(self.file_name, "a") as f:
                print(*args, **kwargs, file=f)

class GreedyFuture(Scheduler.Scheduler):
    def __init__(self,type_scheduler, resources,duty_cycle="blocked", consider_all_gw=True, debug_file="debug_log.txt", lost_thres=5):
        super().__init__(type_scheduler,consider_all_gw)
        self.debug = Config(debug_file)
        self.schedule = {}
        self.debug.debug_log("GreedyFuture scheduler initialized successfully!")

        self.resources = resources
        self.duty_cycle = duty_cycle  # Can be "blocked" or "budget"
        self.next_available_time = {}
        self.total_counts = 0  # Total number of trials for bandit algorithm
        self.available_options = []  # Store available options for each gateway
        self.gateway_inter_time = {}
        self.arrival_per_ed_gw = {}
        self.SF_thres = 9
        self.count = 0
        self.arrivals_per_gw_per_ED = {}
        
        self.lost_thres = lost_thres        

        # ADD THIS LINE:
        self.recent_scheduling_times = {}  # Track scheduling times for load calculation
        # ADD THIS LINE:
        self.recent_scheduling_times = {}  # Track scheduling times for load calculation
        if os.path.exists(self.debug.file_name):
            os.remove(self.debug.file_name)
    def initialize_options(self):
        self.debug.debug_log("Initializing options for gateways")
        for gw in self.gateways:
            for rx in range(2):  # Assuming 2 Rx windows
                self.acumualted_blocked[(gw, rx)] = 0   
                

            self.gateway_inter_time[gw] = []

    def select_option_budget(self,options_gw,sf):

        inter_arrival_times = {}
        for gw in options_gw:
            if len(self.gateway_inter_time[gw]) >=2:
                inter_arrival_times[gw] = np.diff(self.gateway_inter_time[gw])
            else:
                inter_arrival_times[gw] = 0

        # Compute blocking time for each gateway considering both RX windows
        blocking_times = {}
        for gw in options_gw:
            # Calculate blocking time for RX1 (uses same SF as uplink)
            rx1_blocking =  self.TimeOnAir(self.payload_size, sf)/1000 
            
            # Calculate blocking time for RX2 (typically uses SF12)
            rx2_blocking =  self.TimeOnAir(self.payload_size, 12)/1000
            
            
            sum_inter_arrival = np.sum(inter_arrival_times[gw]) if isinstance(inter_arrival_times[gw], np.ndarray) else 0
            avg_inter_arrival = sum_inter_arrival / len(inter_arrival_times[gw]) if isinstance(inter_arrival_times[gw], np.ndarray) and len(inter_arrival_times[gw]) > 0 else 0
            
            std_dev = np.std(inter_arrival_times[gw]) if isinstance(inter_arrival_times[gw], np.ndarray) else 0
            blocked_in_rx1 = rx1_blocking / avg_inter_arrival if avg_inter_arrival > 0 else 0
            blocked_in_rx2 = rx2_blocking / avg_inter_arrival if avg_inter_arrival > 0 else 0
            blocking_times[gw]= {
                'rx1': blocked_in_rx1,
                'rx2': blocked_in_rx2,
            }

            self.debug.debug_log(f"Gateway {gw} - RX1 Blocking: {blocked_in_rx1}, RX2 Blocking: {blocked_in_rx2}, SF: {sf}")
        # Select gateway and RX window that minimize blocked packets
        min_blocked = float('inf')
        action = None

        # Sort all (gw, rx) combinations by blocking time in ascending order
        sorted_options = []
        for gw in options_gw:
            sorted_options.append((gw, 0, blocking_times[gw]['rx1']))
            sorted_options.append((gw, 1, blocking_times[gw]['rx2']))
        
        # Sort by blocking time (ascending)
        sorted_options.sort(key=lambda x: x[2])
        
        # Return array of all options sorted by blocking time (ascending)
        if sorted_options:
            action = [(gw, rx,blocked) for gw, rx, blocked in sorted_options]
            self.debug.debug_log(f"Sorted actions by blocking time (ascending): {[(gw, rx, blocked) for gw, rx, blocked in sorted_options]}")
        else:
            action = []
        
        return action
    

    
    def select_option(self,options_gw,sf):

        inter_arrival_times = {}
        for gw in options_gw:
            if len(self.gateway_inter_time[gw]) >=2:
                inter_arrival_times[gw] = np.diff(self.gateway_inter_time[gw])
            else:
                inter_arrival_times[gw] = 0

        # Compute blocking time for each gateway considering both RX windows
        blocking_times = {}
        for gw in options_gw:
            # Calculate blocking time for RX1 (uses same SF as uplink)
            rx1_blocking =  100*self.TimeOnAir(self.payload_size, sf)/1000 
            
            # Calculate blocking time for RX2 (typically uses SF12)
            rx2_blocking =  10*self.TimeOnAir(self.payload_size, 12)/1000
            
            sum_inter_arrival = np.sum(inter_arrival_times[gw]) if isinstance(inter_arrival_times[gw], np.ndarray) else 0
            #avg_inter_arrival = sum_inter_arrival / len(inter_arrival_times[gw])
            avg_inter_arrival = np.average(inter_arrival_times[gw]) if isinstance(inter_arrival_times[gw], np.ndarray) else 0
            std_dev = np.std(inter_arrival_times[gw]) if isinstance(inter_arrival_times[gw], np.ndarray) else 0
            blocked_in_rx1 = rx1_blocking / avg_inter_arrival if avg_inter_arrival > 0 else 0
            blocked_in_rx2 = rx2_blocking / avg_inter_arrival if avg_inter_arrival > 0 else 0
            blocking_times[gw]= {
                'rx1': blocked_in_rx1,
                'rx2': blocked_in_rx2,
            }

            self.debug.debug_log(f"Gateway {gw} - RX1 Blocking: {blocked_in_rx1}, RX2 Blocking: {blocked_in_rx2}, SF: {sf}")
        # Select gateway and RX window that minimize blocked packets
        min_blocked = float('inf')
        action = None

        # Sort all (gw, rx) combinations by blocking time in ascending order
        sorted_options = []
        for gw in options_gw:
            sorted_options.append((gw, 0, blocking_times[gw]['rx1']))
            sorted_options.append((gw, 1, blocking_times[gw]['rx2']))
        
        # Sort by blocking time (ascending)
        sorted_options.sort(key=lambda x: x[2])
        
        # Return array of all options sorted by blocking time (ascending)
        if sorted_options:
            action = [(gw, rx,blocked) for gw, rx, blocked in sorted_options]
            self.debug.debug_log(f"Sorted actions by blocking time (ascending): {[(gw, rx, blocked) for gw, rx, blocked in sorted_options]}")
        else:
            action = []
        
        return action
    
   

   
    def computeArrivalTimes(self,frame):
        sender = frame.senderId
        receivedTime = frame.receivedTime
        receivedTimeLast = 0 
        if sender not in self.arrivals_per_gw_per_ED:
            self.arrivals_per_gw_per_ED[sender] = {'InterArrivalTimes': [], 'LastarrivalTime': 0, 'Fcnt_last': 0}
        receivedTimeLast = self.arrivals_per_gw_per_ED[sender]['LastarrivalTime']
        missing_arrival_times = []
        if self.arrivals_per_gw_per_ED[sender]['Fcnt_last']+1 < frame.fcnt:
            missing = frame.fcnt - self.arrivals_per_gw_per_ED[sender]['Fcnt_last']
            
            for m in range(missing):
                arrivalTime = (receivedTime-receivedTimeLast)/ missing
                self.arrivals_per_gw_per_ED[sender]['InterArrivalTimes'].append(arrivalTime)
                missing_arrival_times.append(receivedTimeLast + arrivalTime)

        else: 
            self.arrivals_per_gw_per_ED[sender]['InterArrivalTimes'].append(frame.receivedTime - self.arrivals_per_gw_per_ED[sender]['LastarrivalTime'])
        missing_arrival_times.append(frame.receivedTime)
        self.arrivals_per_gw_per_ED[sender]['LastarrivalTime'] = frame.receivedTime
        self.arrivals_per_gw_per_ED[sender]['Fcnt_last'] = frame.fcnt
        return missing_arrival_times



    def schedule_downlink(self, frames, gateways):

        gw_received_UL = [] #tuple of gateway that received the uplink frame (which is the same)
        sender = frames[0].senderId
        received_gws = []
        final_options = {}
        failed = []
        self.count +=1
        ul_gateways = [(frame.receiverID, frame.senderId, frame.SNR, frame) for frame in frames]
        ul_gateways.sort(key=lambda x: x[2], reverse=True)

        missing_arrival_times = self.computeArrivalTimes(frames[0])
        for frame_set in ul_gateways:
            
            self.gateway_inter_time[frame_set[0]].extend(missing_arrival_times)
            gw_received_UL.append((frame_set[0],frame_set[2]))
            received_gws.append(frame_set[0])
            if self.count < EPOCHS:
                if frame_set[3].SF <= self.SF_thres:
                    final_options[(frame_set[0],0)] = self.DownlinkFrame(sender, frame_set[0], frames[0], 0)
                elif frame_set[3].SF >= self.SF_thres:
                    final_options[(frame_set[0],1)] = self.DownlinkFrame(sender, frame_set[0], frames[0], 1)
                
        if self.count > EPOCHS:
            if self.duty_cycle == "blocked":
                actions = self.select_option(received_gws,frames[0].SF)
            else:
                actions = self.select_option_budget(received_gws,frames[0].SF)
            thres =self.lost_thres

            for action in actions:
                if action[2] < thres:  # Only consider options with blocking time less than threshold
                    final_options[(action[0],action[1])] = self.DownlinkFrame(sender, action[0], frames[0], action[1])




        # Update trials for selected gateway
        gw_snr = [gw for gw,_,_,_ in ul_gateways]
        # Sort final_options according to the order of gateways in gw_snr
        ordered_final_options = {}
        for gw in gw_snr:
            for (chosen_gw_id, chosen_rx) in final_options:
                if chosen_gw_id == gw:
                    ordered_final_options[(chosen_gw_id, chosen_rx)] = final_options[(chosen_gw_id, chosen_rx)]
        final_options = ordered_final_options
        for (chosen_gw_id, chosen_rx) in final_options:
            chosen_dl_frame = final_options[(chosen_gw_id, chosen_rx)]
            conflict = self.check_conflicts(chosen_dl_frame, gateways[chosen_gw_id]) 
            if not conflict:
                if self.duty_cycle == 'blocked':
                    blocked = self.check_duty_cycle(chosen_dl_frame, gateways[chosen_gw_id], chosen_rx,False)
                else:
                    blocked = self.check_duty_cycle_budget(chosen_dl_frame, gateways[chosen_gw_id], chosen_rx,False)
                if blocked:
                    gateways[chosen_gw_id].dl_queue_update(chosen_dl_frame)
                    self.schedule[chosen_gw_id] = chosen_dl_frame

                    return chosen_gw_id, chosen_dl_frame, None, frames[0]
       

        #print("No available options to schedule downlink.")            

        return None, None, failed, None

 
