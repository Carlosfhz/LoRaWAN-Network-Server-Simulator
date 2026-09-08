import math

from NS_Simulator import Scheduler
import numpy as np

DEBUG = False
UNITARY = True
def debug_log(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


class SchedulerBudgetGreedyEntropy_RSSI_v2(Scheduler.Scheduler):
    """
    Budget-Aware Greedy Downlink Scheduler
    Maximizes the number of successful downlink transmissions
    under gateway-specific duty cycle budget constraints.
    """
    #(1.7,0.15,0.35,0.2,0.3,0.1) #SF_IMPACT,W_SNR,W_BLOCK,W_RATE,W_AVAIL,GAMMA
    def __init__(self, type_scheduler, resources, duty_cycle="blocked", consider_all_gw=True, SF_IMPACT= 0.0,W_RSSI = 0.33, W_SNR=0.33, W_BLOCK=0.34, W_RATE=1, W_AVAIL=1, GAMMA=0.1,THRESHOLD_BLOCKED=0):
        super().__init__(type_scheduler, consider_all_gw)
        self.resources = resources
        self.duty_cycle = duty_cycle  # "blocked" or "budget"
        # Default duty cycle budgets (sec/hour) if not supplied
        self.duty_cycle_budget = {"rx1": 36.0, "rx2": 360.0}
        self.budget_remaining = {}  # Remaining budgets per GW & Rx
        self.rate_per_SF = {7: 0, 8: 0, 9: 0, 10: 0, 11: 0, 12: 0}  # Packets per second per SF
        self.sensitivity_map = {7:-7.5, 8:-10, 9:-12.5, 10:-15, 11:-17.5, 12:-20}
        self.rssi_per_gw= {}   
        self.total_sf = []
        self.schedule = {}
        self.ENTROPY_WINDOW = 100
        self.current_entropy = []
        self.measures_for_weight = {'snr': [], 'block': [], 'rate': [], 'avail': [], 'rssi': []}
        self.measures_entropy = {'snr': [], 'block': [], 'rate': [], 'avail': [], 'rssi': []}
        self.measures_p = {'snr': [], 'block': [], 'rate': [], 'avail': [], 'rssi': []}

        n_measures = 0
        self.SF_IMPACT = SF_IMPACT
        self.W_SNR = W_SNR
        self.W_BLOCK = W_BLOCK
        self.W_RATE = W_RATE
        self.W_AVAIL = W_AVAIL
        self.GAMMA = GAMMA
        self.W_RSSI = W_RSSI
        self.snr_margin_per_ed = {}
        self.snr_margin_per_gw = {}
        self.rssi_per_ed = {}

        self.THRESHOLD_BLOCKED = THRESHOLD_BLOCKED  # Minimum budget to allow scheduling
        self.next_available_time = {}

    def initialize_options(self):
        debug_log("Initializing gateway options and budgets...")
        for gw in self.gateways:
            for rx in range(2):  # Rx1 and Rx2
                option = (gw, rx)
                self.available_options.append(option)
                self.StateOptions[(gw, rx)] = None
                # Initialize full duty cycle budget
                rx_key = "rx1" if rx == 0 else "rx2"
                self.budget_remaining[(gw, rx)] = self.duty_cycle_budget[rx_key]
                self.acumualted_blocked[option] = 0

            self.snr_margin_per_gw[gw] = []
            self.rssi_per_gw[gw] = []
    def schedule_downlink(self, frames, gateways):
        """
        Greedy priority-based scheduler selecting the best feasible (GW, Rx) option.
        """
        frame = frames[0]
        ed_id = frames[0].senderId
        arrived_time = frames[0].receivedTime
        ul_gateways = []
        

        N_available = 0
        for frame_x in frames:
            N_ava, _, _ = self.get_available_options(frame_x)
            N_available += N_ava
            ul_gateways.append((frame_x.receiverID, frame_x.senderId, frame_x.SNR,frame_x.RSSI, frame_x))

        ul_gateways.sort(key=lambda x: x[2], reverse=True)  # Sort by SNR descending
        sf = frame.SF
        self.total_sf.append(sf)
        self.rate_per_SF[sf] += 1 

        current_rate_sf = self.rate_per_SF[sf] / (arrived_time + 1e-6)  # Avoid div by zero
        median = np.median(self.total_sf)
        final_options = {}
        rssi_snr_gw_registered = []
        for gw_id, rx in self.available_options:
            
            frame_dl = self.DownlinkFrame(ed_id, gw_id, frame, rx)
            #N_available, N_available_rx1, N_available_rx2 = self.get_available_options(frame)
            toa = self.TimeOnAir(self.payload_size,frame_dl.SF)/1000  # ToA in seconds
            blocking_time = 99*toa if rx == 0 else 9*self.TimeOnAir(self.payload_size,12)/1000  # I use this but I know is not the blocked time
                               
            didReceivedUL = any(gw_id == uplink[0] for uplink in ul_gateways)

                
            if didReceivedUL:
                # extract SNR from the matching uplink entry (receiverID == gw_id)
                RSSI = next((uplink[3] for uplink in ul_gateways if uplink[0] == gw_id), None)
                SNR = next((uplink[2] for uplink in ul_gateways if uplink[0] == gw_id), None)
            else:
                RSSI = -200  # Default low RSSI if no uplink received
                SNR = -200  # Default low SNR if no uplink received

            if (ed_id, gw_id) not in self.snr_margin_per_ed:
                self.snr_margin_per_ed[(ed_id, gw_id)] = []


            if (ed_id, gw_id) not in self.rssi_per_ed:
                self.rssi_per_ed[(ed_id, gw_id)] = []
            #vector = current_rate_sf, median, SNR, blocking_time ,frame_dl
            duty_cycle_in = None
            if (didReceivedUL or (rx == 1 and self.consider_all_gw)) and N_available > 0:
                if gw_id not in rssi_snr_gw_registered:
                    rssi_snr_gw_registered.append(gw_id)
                    self.rssi_per_ed[(ed_id, gw_id)].append(RSSI)
                    self.rssi_per_gw[gw_id].append(RSSI)
                    self.snr_margin_per_gw[gw_id].append(abs(SNR - self.sensitivity_map[sf]))
                    self.snr_margin_per_ed[(ed_id, gw_id)].append(abs(SNR - self.sensitivity_map[sf]))
                if self.duty_cycle == 'budget':
                    duty_cycle_in = gateways[gw_id].available_tx_time[rx + 1]
                priority = self.compute_priority(current_rate_sf, blocking_time, self.rssi_per_ed[(ed_id, gw_id)], self.snr_margin_per_ed[(ed_id, gw_id)],gw_id, rx, median, sf, duty_cycle=duty_cycle_in, N_available=N_available,didReceivedUL=didReceivedUL)
                final_options[(gw_id, rx)] = (priority,frame_dl)
        # Sort final_options by priority (highest first) and pick the top candidate
        sorted_options = sorted(final_options.items(), key=lambda kv: kv[1][0], reverse=True)



        # Select the best option based on computed prioritiesbest_candidate = (gw_id, chosen_dl_frame)
        if final_options:
            for (gw_id, rx), (priority, chosen_dl_frame) in sorted_options:
                conflict = self.check_conflicts(chosen_dl_frame, gateways[gw_id])
                if not conflict and priority > self.THRESHOLD_BLOCKED:
                    if self.duty_cycle == 'blocked':
                        blocked = self.check_duty_cycle(chosen_dl_frame, gateways[gw_id], rx,False)
                    else:
                        blocked = self.check_duty_cycle_budget(chosen_dl_frame, gateways[gw_id], rx,False)
                    if blocked:
                        gateways[gw_id].dl_queue_update(chosen_dl_frame)
                        self.schedule[gw_id] = chosen_dl_frame
                        return gw_id, chosen_dl_frame, None, frames[0]
                    else:
                        continue

        return None, None, None, None

    



            

    # -------------------
    # Helper methods
    # -------------------



    def compute_priority(self, current_rate_sf, blocking_time, RSSI, SNR_m,gw_id, rx, median, sf,duty_cycle=None, N_available=None, didReceivedUL=None):
        """
        Compute a scalar priority (higher is better).

        Inputs:
        - current_rate_sf: packets/sec for this SF (higher -> lower priority to balance load)
        - blocking_time: seconds the GW will be blocked (lower is better)
        - RSSI: measured RSSI for the GW (higher is better)
        - rx: 0 for Rx1, 1 for Rx2 (we prefer Rx1 for low SF and Rx2 for high SF)
        - median: median SF value used as the threshold between low/high SF
        - sf: the frame's SF (used for rx preference)
        - N_available: optional number of other available options (higher -> more alternatives)
          NOTE: now lower availability (few alternatives) should reduce priority, especially when blocking_time is high.
        """
        self.current_entropy
        # safe defaults / guards
        if blocking_time is None:
            blocking_time = 0.0
        if current_rate_sf is None:
            current_rate_sf = 0.0
        if RSSI is None:
            RSSI = -200.0
        if N_available is None:
            N_available = 0

        # 5) Availability handling:
        #    N_available = number of other alternatives (higher => more choices).
        #    We want lower availability to reduce priority, and do so more strongly when blocking_time is high.
        #    avail_norm in [0,1) increases with number of alternatives.
        #avail_norm = N_available / len(self.available_options) 

        #) Normalize SNR_margin into [0,1] assuming plausible range [-20, +20] dB
        snr_margin_avg  =np.mean(SNR_m[-20:]) if SNR_m else 0.0
        snr_margin_norm = (snr_margin_avg - min(self.snr_margin_per_gw[gw_id])) / (max(self.snr_margin_per_gw[gw_id]) - min(self.snr_margin_per_gw[gw_id]) + 1e-6)
        #snr_margin_norm = (SNR_m + 20) / 40.0
        snr_margin_norm = max(0.0, min(1.0, snr_margin_norm))

        # 1) Normalize RSSI into [0,1] assuming plausible range [-200, +200] dB
        RSSI_aver = np.mean(RSSI[-20:]) if RSSI else -200.0
        rssi_norm = (RSSI_aver - min(self.rssi_per_gw[gw_id])) / (max(self.rssi_per_gw[gw_id]) - min(self.rssi_per_gw[gw_id]) + 1e-6)
        rssi_norm = max(0.0, min(1.0, rssi_norm))

        toa_sf = self.TimeOnAir(self.payload_size, sf) / 1000
        toa_sf7 = self.TimeOnAir(self.payload_size, 7) / 1000
        toa_sf12 = self.TimeOnAir(self.payload_size, 12) / 1000
        toa_norm = (toa_sf - toa_sf7) / (toa_sf12 - toa_sf7 + 1e-6)
        toa_norm = max(0.0, min(1.0, toa_norm))

        # In Rx2 we keep the conservative SF12 budget consumption assumption.
        consumed = toa_sf if rx == 0 else toa_sf12
        budget_window = self.duty_cycle_budget["rx1"] if rx == 0 else self.duty_cycle_budget["rx2"]
        if duty_cycle is None:
            remaining_norm = 0.0
        else:
            remaining_norm = (duty_cycle - consumed/N_available) / (budget_window + 1e-6)

        # Benefit term:
        # - penalize sending high-ToA frames in Rx1 (they block a scarce 1% window)
        # - reward sending high-ToA frames in Rx2
        # - keep a non-zero floor for Rx2 so low-SF packets can still be scheduled there
        if rx == 0:
            window_benefit = 1.0 - toa_norm if N_available > 0 else 1.0
        else:
            window_benefit = 1.0 

        #block_norm = (max_block- blocking_time ) / (max_block - min_block)  # Inverted so that smaller blocking_time -> higher score
        # Normalize blocking by its window worst case
        #block_norm = self.compute_reward_old(sf,rx)

        min_block = 99*toa_sf7 
        max_block = 99*toa_sf12 


        #block_score = 1.0 - (blocking_time - min_block) / (max_block - min_block + 1e-6)  # Inverted so that smaller blocking_time -> higher score
        if self.duty_cycle == 'blocked':
            remaining_norm = 1.0 - (blocking_time - min_block) / (max_block - min_block + 1e-6)  # Inverted so that smaller blocking_time -> higher score
            window_benefit = 1
        
        block_norm = remaining_norm * window_benefit

        block_norm = max(0.0, min(1.0, block_norm))

        # 3) Rate balancing: prefer SFs with lower current rate
        #rate_score = 1.0 / (1.0 + current_rate_sf)




        #    Apply a blocking-dependent penalty to availability: when blocking_time is large,
        #    the availability contribution is further reduced.
        #    gamma is a tunable sensitivity constant (higher -> stronger penalty from blocking_time).
        #gamma = self.GAMMA
        #block_penalty_on_avail = 1.0 / (1.0 + gamma * blocking_time)

        #avail_score = avail_norm * block_penalty_on_avail
        # 4) Rx preference based on SF relative to median:
        if rx == 0 and didReceivedUL and (sf <= median):
            rx_pref = 1 
        elif rx == 1 and didReceivedUL:
            rx_pref = 1
        elif rx == 0 and didReceivedUL and (sf >= median):
            rx_pref = 1 - self.SF_IMPACT

        # else:
        #     print(didReceivedUL, rx, sf, median)


        #base_score = (self.W_BLOCK * block_score)  + (self.W_RSSI * rssi_norm) + self.W_SNR * snr_margin_norm
        w_block,w_rssi,w_snr = 0,0,0
        if len(self.measures_for_weight['rssi']) < self.ENTROPY_WINDOW or UNITARY:
            self.measures_for_weight['rssi'].append(RSSI[-1])
            self.measures_for_weight['snr'].append(SNR_m[-1])
            self.measures_for_weight['block'].append(block_norm)
            #self.measures_for_weight['rate'].append(current_rate_sf)
            #self.measures_for_weight['avail'].append(avail_score)
            base_score = (self.W_BLOCK * block_norm)  + (self.W_RSSI * rssi_norm) + self.W_SNR * snr_margin_norm
        else:
            self.measures_for_weight['rssi'].append(RSSI[-1])
            self.measures_for_weight['snr'].append(SNR_m[-1])
            self.measures_for_weight['block'].append(block_norm)
            #self.measures_for_weight['rate'].append(current_rate_sf)
            #self.measures_for_weight['avail'].append(N_available)
            e_rssi = self.Compute_entropy_weight('rssi', RSSI[-1])
            e_snr = self.Compute_entropy_weight('snr', SNR_m[-1])
            e_block = self.Compute_entropy_weight('block', block_norm)
            #rate_score_adj = self.Compute_entropy_weight('rate', rate_score)
            #avail_score_adj = self.Compute_entropy_weight('avail', avail_score)
            w_rssi, w_snr, w_block = self.compute_weights([e_rssi, e_snr, e_block])
            base_score =  w_block * block_norm  + w_rssi * rssi_norm + w_snr * snr_margin_norm

        # Apply rx preference as a multiplier to bias selection towards the intended window
        final_score = base_score * rx_pref
        #print(f"W_snr: {w_snr}, W_block: {w_block}, W_rssi: {w_rssi}, Rx_pref: {rx_pref}")
        #print(f"Scheduling SF {sf}, GW {gw_id}, Rx {rx} - SNR Margin: {snr_margin_avg:.2f}, RSSI: {RSSI_aver:.2f}, Rssi_norm: {rssi_norm:.2f}, SNR_norm: {snr_margin_norm:.2f}, Block Score: {block_norm:.2f}, Final Priority: {final_score:.4f}"    )
        return float(final_score)
        



    def compute_reward_old(self, original_sf,Rx):
            """
            Calculates a reward based on the log-normalized distance 
            from SF7 (default, reward=0 for SF7, 1 for SF12) 
            or from SF12 (reward=1 for SF7, 0 for SF12).

            Parameters:
                toa_x (float): Time on air for the current SF
                toa_sf7 (float): Time on air for SF7
                toa_sf12 (float): Time on air for SF12
                from_sf12 (bool): If True, reward is 1 for SF7, 0 for SF12

            Returns:
                float: Scaled reward between 0 and 1
            """
            toa_sf7 = self.TimeOnAir(self.payload_size, 7)/1000
            toa_sf12 = self.TimeOnAir(self.payload_size, 12)/1000

            toa_x = self.TimeOnAir(self.payload_size, original_sf)/1000
            multi = 1



            log_sf7 = math.log(toa_sf7)
            log_sf12 = math.log(toa_sf12)
            log_x = math.log(toa_x)
            denom = log_sf12 - log_sf7

            if Rx == 1:
                return (1 - (log_sf12 - log_x) / denom) 
            else:
                return (1 - (log_x - log_sf7) / denom) 


    def Compute_entropy_weight(self, metric, xij):
        eps = 1e-12

        # keep only last N samples (online, no need for final dataset size)
        samples = self.measures_for_weight[metric][-self.ENTROPY_WINDOW:]
        x = np.asarray(samples, dtype=float)

        if x.size <= 1:
            return 0.0

        # shift if negatives exist, then normalize to probabilities
        xmin = np.min(x)
        if xmin < 0:
            x = x - xmin + eps
        else:
            x = x + eps

        p = x / (np.sum(x) + eps)  # valid probability vector
        H = -np.sum(p * np.log(p + eps)) / np.log(len(p) + eps)  # normalized entropy
        return float(np.clip(H, 0.0, 1.0))

    def compute_weights(self, entropies):
        e = np.asarray(entropies, dtype=float)
        e = np.nan_to_num(e, nan=1.0, posinf=1.0, neginf=0.0)
        e = np.clip(e, 0.0, 1.0)

        inv = 1.0 - e
        total = float(np.sum(inv))

        if total <= 1e-12:
            # fallback: equal weights
            w = np.full_like(inv, 1.0 / len(inv)) if len(inv) > 0 else np.array([])
        else:
            w = inv / total

        # force exact sum=1 (avoid floating residue)
        if w.size > 0:
            w[-1] = 1.0 - float(np.sum(w[:-1]))

        print(f"[WEIGHTS] entropies={e.tolist()} weights={w.tolist()} sum={float(np.sum(w)):.12f}")
        return w.tolist()