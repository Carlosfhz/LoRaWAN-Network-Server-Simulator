import os
from NS_Simulator import Scheduler
import math
import numpy as np
from Schedulers.OptimalSchedulling_Portable import OptimalSchedulling_Portable

DEBUG= False  # Set to False for production performance

EPOCHS = 20
LOAD = 20  # Number of packets to simulate
MOMENTS = 100
HORIZON = 120
np.set_printoptions(suppress=True, precision=8)
class Config:
    def __init__(self,debug_file):
        self.file_name = debug_file

    def debug_log(self, *args, **kwargs):
        if DEBUG:
            print(*args, **kwargs)
            with open(self.file_name, "a") as f:
                print(*args, **kwargs, file=f)

class GreedyFuture_Rolling_Horizon_complete_v3(Scheduler.Scheduler):
    def __init__(self,type_scheduler, resources,duty_cycle="blocked", consider_all_gw=True, debug_file="debug_log.txt", lost_thres=3):
        super().__init__(type_scheduler,consider_all_gw)
        self.debug = Config(debug_file)
        self.schedule = {}
        self.debug.debug_log("GreedyFuture scheduler initialized successfully!")
        self.optimal_scheduler = OptimalSchedulling_Portable(duty_cycle,HORIZON)
        self.resources = resources
        self.duty_cycle = duty_cycle  # Can be "blocked" or "budget"
        self.next_available_time = {}
        self.total_counts = 0  # Total number of trials for bandit algorithm
        self.available_options = []  # Store available options for each gateway
        self.gateway_inter_time = {}
        self.arrivals_per_gw_per_ED = {}
        self.gateway_inter_time_all = {}

        self.SF_thres = 9
        self.count = 0
        
        self.lost_thres = lost_thres        
        
        # Add TimeOnAir cache for performance
        self.toa_cache = {}
        
        self.recent_scheduling_times = {}  # Track scheduling times for load calculation
        if os.path.exists(self.debug.file_name):
            os.remove(self.debug.file_name)
            
    def get_cached_toa(self, payload_size, sf):
        """Cached TimeOnAir calculation for performance"""
        key = (payload_size, sf)
        if key not in self.toa_cache:
            self.toa_cache[key] = self.TimeOnAir(payload_size, sf)
        return self.toa_cache[key]
        
    def initialize_options(self):
        self.debug.debug_log("Initializing options for gateways")
        for gw in self.gateways:
            for rx in range(2):  # Assuming 2 Rx windows
                self.acumualted_blocked[(gw, rx)] = 0   
                

            self.gateway_inter_time[gw] = {7:[],8:[],9:[],10:[],11:[],12:[]}
            self.gateway_inter_time_all[gw] = []

    
    def predicting_packets(self, gw, sf, current_time, prediction_horizon):
        """
        Predict packet arrival times using deterministic mean intervals
        
        Returns:
            list: List of predicted arrival times within the prediction horizon
        """
        # Validation
        if (gw not in self.gateway_inter_time or 
            sf not in self.gateway_inter_time[gw] or 
            len(self.gateway_inter_time[gw][sf]) < 2):
            return []
        
        arrival_times = self.gateway_inter_time[gw][sf]
        
        # Calculate arrival rate (λ) using Maximum Likelihood Estimation
        inter = np.diff(arrival_times)
        observation_window = sum(inter)
        if observation_window <= 0:
            return []
        
        arrival_rate = len(inter) / observation_window  # packets per time unit
        
        predicted_arrivals = []
        next_time = self.gateway_inter_time[gw][sf][-1]
        horizon_end = current_time + prediction_horizon
        #mean_inter = np.average(inter)
        while next_time < horizon_end:


            inter_arrival = 1/arrival_rate
            next_time += inter_arrival
            
            if next_time <= horizon_end and next_time-self.get_cached_toa(self.payload_size+20, sf)/1000 > current_time:
                predicted_arrivals.append(next_time)
        
        self.debug.debug_log(f"Gateway {gw}, SF {sf}: {len(predicted_arrivals)} predictions")
        return predicted_arrivals
    

    def compute_max_arrivals(self, options_gw,in_sf, usable_rx,frames):

        if self.duty_cycle == "blocked":
            bt_rx1 = 100*self.get_cached_toa(self.payload_size, in_sf)/ 1000
            bt_rx2 = 10*self.get_cached_toa(self.payload_size, 12)/ 1000
        else:
            bt_rx1 = HORIZON
            bt_rx2 = HORIZON

        # Limit horizon for performance - reduce from max to a reasonable window
        max_horizon = max(bt_rx1,bt_rx2) 
        #max_horizon = 120
        Uc_n = {}
        ed_sf = {}
        start_time_UL_real = frames[0].sendTime
        end_time_UL_real = frames[0].receivedTime
        self.debug.debug_log(f"uplink real start time: {start_time_UL_real}, end time: {end_time_UL_real}, max horizon: {max_horizon}")
        cnt = 1
        Uc_n[0] = {}
        ed_sf[0] = in_sf

        if start_time_UL_real not in Uc_n[0]:
                Uc_n[0][start_time_UL_real] = []
        for gw in options_gw:
            if usable_rx is None or usable_rx[gw]==[]: # This means that neither rx1 or Rx2 are avaialable for downlink scheduling.
                continue
    

            tnj_g = (gw, (start_time_UL_real, end_time_UL_real))
            Uc_n[0][start_time_UL_real].append(tnj_g)
            
            
            for sf in self.gateway_inter_time[gw]:

                if len(self.gateway_inter_time[gw][sf])<=1:
                    continue


                self.debug.debug_log(f"Gateway inter-arrival times: {self.gateway_inter_time[gw][sf]}")
               
                ul_start = 0

                predicted_arrivals = self.predicting_packets(gw, sf, end_time_UL_real, max_horizon)
                
                toa_ul = self.get_cached_toa(self.payload_size+20, sf)/1000
                
                for arrival_time in predicted_arrivals:
                    ul_end = arrival_time
                    ul_start = ul_end - toa_ul
                    if cnt not in Uc_n:
                        Uc_n[cnt] = {}
                        ed_sf[cnt] = sf
                    if ul_start not in Uc_n[cnt]:
                        Uc_n[cnt][ul_start] = []

                    tnj_g = (gw, (ul_start, ul_end))
                    Uc_n[cnt][ul_start].append(tnj_g)

                    

                    cnt += 1

        self.debug.debug_log(f"Computed Uc_n with {len(Uc_n)} scenarios:")
        for scenario_id, scenario_data in Uc_n.items():
            sf = ed_sf.get(scenario_id, 'N/A')
            for time_key, arrivals in scenario_data.items():
                gateway_info = [f"GW{gw}:{start:.3f}-{end:.3f}" for gw, (start, end) in arrivals]
                self.debug.debug_log(f"  Scenario {scenario_id} (SF={sf}): t={time_key:.3f} -> {gateway_info}")
        return Uc_n, ed_sf

    
        

        

                    
                    
    


    def select_option(self,options_gw,sf, usable_rx,frames,gw_max_snr,send):
        
        Uc_n, ed_sf= self.compute_max_arrivals(options_gw,sf,usable_rx,frames)
        options = self.optimal_scheduler.LIP_problem(Uc_n, ed_sf,usable_rx,gw_max_snr,send)
        #compute number of optimal schedulings per gw and rx window
        #compute number of optimal schedulings per gw and rx window
        
        self.debug.debug_log(f"Optimization results - {self.optimal_scheduler.extract_results(Uc_n)} ")
        
        return options
    
   
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
        usable_rx = None
        final_options = {}
        failed = []
        self.count +=1
        ul_gateways = [(frame.receiverID, frame.senderId, frame.SNR, frame) for frame in frames]
        ul_gateways.sort(key=lambda x: x[2], reverse=True)
        missing_arrival_times = self.computeArrivalTimes(frames[0])

        for frame_set in ul_gateways:
            self.gateway_inter_time[frame_set[0]][frames[0].SF].extend(missing_arrival_times)
            self.gateway_inter_time_all[frame_set[0]].extend(missing_arrival_times)
            #self.gateway_inter_time[frame_set[0]][frames[0].SF].sort()
            #self.gateway_inter_time_all[frame_set[0]].sort()
            gw_received_UL.append((frame_set[0],frame_set[2]))
            if self.count < EPOCHS:
                if frame_set[3].SF <= self.SF_thres:
                    final_options[(frame_set[0],0)] = self.DownlinkFrame(sender, frame_set[0], frames[0], 0)
                elif frame_set[3].SF >= self.SF_thres:
                    final_options[(frame_set[0],1)] = self.DownlinkFrame(sender, frame_set[0], frames[0], 1)
            else:
                frames_in_rx1_and_rx2 = [self.DownlinkFrame(sender, frame_set[0], frames[0], 0),self.DownlinkFrame(sender, frame_set[0], frames[0], 1)]
                av_rx = [0,0]
                for i in range(2):
                    
                    conflict = self.check_conflicts(frames_in_rx1_and_rx2[i], gateways[frame_set[0]]) 
                    if self.duty_cycle == "blocked":
                        blocked = self.check_duty_cycle(frames_in_rx1_and_rx2[i], gateways[frame_set[0]], i,True)
                    else:
                        blocked = self.check_duty_cycle_budget(frames_in_rx1_and_rx2[i], gateways[frame_set[0]], i,True)
                    

                    if not conflict and blocked:
                        
                        final_options[(frame_set[0],i)] = frames_in_rx1_and_rx2[i]
                        av_rx[i] = 1


                if av_rx != [0,0]:
                    if usable_rx is None:
                        usable_rx = {}
                    usable_rx[frame_set[0]] = av_rx
                    received_gws.append(frame_set[0])

            
        gw_snr = [gw for gw,_,_,_ in ul_gateways]
        if self.count > EPOCHS and final_options!={}:

            final_options_copy = final_options.copy()
            final_options = {}
            options = self.select_option(received_gws,frames[0].SF,usable_rx,frames,gw_max_snr=gw_snr,send=0)
            for (gw, rx) in options:
                if (gw, rx) in final_options_copy:
                    final_options[(gw, rx)] = final_options_copy[(gw, rx)]
        elif final_options=={}:
            return None, None, failed, None
            
            
            
        
        #print("No available options to schedule downlink.")        
        # 


                # Update trials for selected gateway
        for (chosen_gw_id, chosen_rx) in final_options:
            chosen_dl_frame = final_options[(chosen_gw_id, chosen_rx)]

            conflict = self.check_conflicts(chosen_dl_frame, gateways[chosen_gw_id]) 
            if not conflict:
                if self.duty_cycle == "blocked":
                    blocked = self.check_duty_cycle(chosen_dl_frame, gateways[chosen_gw_id], chosen_dl_frame.rx_window-1,False)
                else:
                    blocked = self.check_duty_cycle_budget(chosen_dl_frame, gateways[chosen_gw_id], chosen_dl_frame.rx_window-1,False)
                if blocked:
                    gateways[chosen_gw_id].dl_queue_update(chosen_dl_frame)
                    self.schedule[chosen_gw_id] = chosen_dl_frame

                    return chosen_gw_id, chosen_dl_frame, None, frames[0]    

        return None, None, failed, None

 
