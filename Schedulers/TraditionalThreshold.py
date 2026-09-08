from NS_Simulator import Scheduler
DEBUG = False
def debug_log(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

class TraditionalThreshold(Scheduler.Scheduler):
    def __init__(self, type_scheduler, resources, threshold, duty_cycle="blocked",consider_all_gw=False):
        super().__init__(type_scheduler,consider_all_gw)
        self.resources = resources
        self.schedule = {}
        self.threshold = threshold
        self.next_available_time = {}
        self.duty_cycle = duty_cycle #Can be "blocked" or "budget"


    def initialize_options(self):
        debug_log("Initializing options for gateways")
        #print("INITIALIZING OPTIONS", self.gateways)
        for gw in self.gateways:
            for rx in range(2):  # Assuming 2 Rx windows
                option = (gw, rx)
                self.available_options.append(option)     
                self.StateOptions[(gw, rx)] = None  # Initialize state for each option
                self.acumualted_blocked[(gw, rx)] = 0




    def schedule_downlink(self, frames, gateways):
        ed_id = frames[0].senderId
        ##### Just checking fictionary reward update for all options before scheduling
        for gw_id, rx in self.available_options:
            dl_tempative = self.DownlinkFrame(ed_id, gw_id, frames[0], rx)
            if self.StateOptions[(gw_id, rx)] is not None:
                final_reward = self.update_reward_after_availability(gw_id,rx,dl_tempative,gateways)
        ##### Just checking fictionary reward update for all options before scheduling
        debug_log("Scheduling downlink for frames:", frames, "Using gateways:", gateways)
        ul_gateways = [(frame.receiverID, frame.senderId, frame.SNR, frame) for frame in frames]
        SF_UL = frames[0].SF
        debug_log("Scheduling downlink for uplink frames:", ul_gateways)
        ul_gateways.sort(key=lambda x: x[2], reverse=True)
        failed = {}
        for data in ul_gateways:
            failed[data[0]] = {}
            for rx in range(len(self.rx_window_delay)):

                if SF_UL > self.threshold and rx ==0:
                    continue
                if SF_UL < self.threshold and rx == 1:
                    continue
                frame_dl = self.DownlinkFrame(data[1], data[0], data[3], rx)
                conflict = self.check_conflicts(frame_dl, gateways[data[0]])
                if not conflict:
                    if self.duty_cycle == "blocked":
                        blocked = self.check_duty_cycle(frame_dl, gateways[data[0]], rx)
                    elif self.duty_cycle == "budget":
                        blocked = self.check_duty_cycle_budget(frame_dl, gateways[data[0]], rx)
                    if blocked:
                        gateways[data[0]].dl_queue_update(frame_dl)
                        self.schedule[data[0]] = frame_dl
                        reward = self.compute_reward(frame_dl.original_SF, rx, True, frame_dl)
                        self.StateOptions[(data[0], rx)] = [reward, 0, True, frame_dl.original_SF]      
                        return data[0], frame_dl, None, data[3]
                    else:
                        ### Imaginary Reward update for options that were not selected but had conflict
                        if self.StateOptions[(data[0], rx)] is not None:
                            self.StateOptions[(data[0], rx)][1] += 1
                        failed[data[0]][rx] = {'Blocked'}
                else:
                    ### Imaginary Reward update for options that were not selected but had conflict
                    for key in self.StateOptions:
                        if key[0] == data[0] and self.StateOptions[key] is not None and self.StateOptions[key][2]:
                            self.StateOptions[key][1] += 1
                    failed[data[0]][rx] = {'Conflict'}
        return None, None, failed, None
