import math
from collections import defaultdict
from .Frame import Frame
from .LoRaGateway import LoRaGateway
from .EndDevice import EndDevice

TX_START_DELAY = 1500
TX_MARGIN_DELAY = 1000
TX_JIT_DELAY = 30000
DEBUG = False

def debug_log(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

class Scheduler:
    def __init__(self, type_scheduler, consider_all_gw, rx_window_delay=[1, 2], payload_size=12, DefaultSF=12):
        self.type_scheduler = type_scheduler
        self.rx_window_delay = rx_window_delay
        self.payload_size = payload_size
        self.DefaultSF = DefaultSF
        self.StateOptions = {}
        self.consider_all_gw = consider_all_gw
        self.acumualted_blocked = {}
        self.available_options = []
        self.ResultLastSchedule = None
        self.prevReward = None
        self.Acumulated_rewards = 0
        self.rewards_history = []
        self.total_sf = []
        self.current_hour = 1
        self.gateways = None

    def DownlinkFrame(self, device_id, gateway_id, UL_frame, Rx_Window):
        SF = UL_frame.SF
        if Rx_Window+1 == 2:
            SF = self.DefaultSF
        time_on_air = self.TimeOnAir(self.payload_size, SF)/1000
        start_time = UL_frame.receivedTime + self.rx_window_delay[Rx_Window]
        end_time = start_time + time_on_air

        return Frame(
            senderId=gateway_id,
            receiverID=device_id,
            sendTime=start_time,
            receivedTime=end_time,
            SF=SF,
            original_SF=UL_frame.SF,
            SNR=float('inf'),
            RSSI=float('inf'),
            Ftype='3',
            fcnt=0,
            rx_window=Rx_Window+1,
            rx_or_tx='tx'
        )
    
    def compute_reward(self, original_sf,Rx,chosen_is_in_received,dl_scheduled):

        num_option_available,num_option_available_rx1,num_option_available_rx2 = self.get_available_options(dl_scheduled)
        weight_sf = self.weight_sf_by_availability(num_option_available, dl_scheduled.SF)
        reward = 0
        if Rx == 0 and original_sf<=9 and chosen_is_in_received:
            reward = 10
        elif Rx == 1 and original_sf>=9 and chosen_is_in_received :
            reward = 10
        elif chosen_is_in_received ==0 and Rx==1:
            reward = 5
        elif (Rx == -1 and original_sf>=9 and num_option_available_rx2 == 0) or (Rx == -1 and original_sf<=9 and num_option_available_rx1 == 0):
            return 0
        else:
            return -10
        return reward*weight_sf


    def weight_sf_by_availability(self, num_options, sf, min_sf=7, max_sf=12, exponent=1.0):
        """
        Compute a weighting factor in [0,1] that combines how many available options there are
        with the chosen spreading factor (SF). The weight reduces more strongly for high SFs
        when available options are low.

        Parameters:
            num_options (int): number of available options (>=0)
            sf (int): spreading factor for the candidate (e.g. 7..12)
            min_sf (int): minimum SF in the system (default 7)
            max_sf (int): maximum SF in the system (default 12)
            exponent (float): optional exponent to increase sensitivity to availability (default 1.0)

        Returns:
            float: weight in range [0,1] (lower means SF has larger negative impact)
        """
        # clamp inputs
        if num_options <= 0:
            return 0.0
        sf = max(min_sf, min(max_sf, sf))

        # availability in [0,1], saturates at `saturation`
        avail = min(1.0, float(num_options) / float(len(self.available_options)))
        # optionally increase sensitivity to availability
        avail = avail ** exponent

        # normalized SF in [0,1] where 0 -> min_sf (best) and 1 -> max_sf (worst)
        norm_sf = (sf - min_sf) / float(max_sf - min_sf)

        # Combine: availability boosts the weight, high SF reduces it proportionally to how scarce options are.
        # weight = avail * (1 - norm_sf * (1 - avail))
        # This ensures:
        #  - if avail == 1.0 -> weight == 1.0 (SF doesn't hurt when many options)
        #  - if avail -> 0.0 -> weight -> 0.0 (scarce options force weight down)
        weight = avail * (1.0 - norm_sf * (1.0 - avail))

        # safety clamp
        return max(0.0, min(1.0, weight))
        
    def get_available_options(self, frame_ul):
        ed_id = frame_ul.senderId
        final_options = []
        final_options_rx1 = []
        final_options_rx2 = []
        for gw,rx in self.available_options:
            if gw != -1:
                frame_dl = self.DownlinkFrame(ed_id, gw, frame_ul, rx)

                conflict = self.check_conflicts(frame_dl,self.gateways[gw])
                duty_ok = self.check_duty_cycle(frame_dl, self.gateways[gw], rx, True)

                if (not conflict) and duty_ok:
                    final_options.append((gw, rx, frame_dl))
                if (not conflict) and duty_ok and rx == 0:
                    final_options_rx1.append((gw, rx, frame_dl))
                if (not conflict) and duty_ok and rx == 1:
                    final_options_rx2.append((gw, rx, frame_dl))

        return len(final_options), len(final_options_rx1), len(final_options_rx2)
        
    def compute_reward_old(self, original_sf,Rx,chosen_is_in_received):
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


    def check_conflicts(self, frame_to_schedule, gateway,give_collission = False):
        for frame_scheduled in gateway.dl_queue:
            existing_start = frame_scheduled.sendTime
            existing_end = frame_scheduled.receivedTime
            started_time = frame_to_schedule.sendTime
            received_time = frame_to_schedule.receivedTime

            if not (received_time + (TX_MARGIN_DELAY / 1e6) <= existing_start - (TX_START_DELAY + TX_JIT_DELAY) / 1e6 or
                    existing_end + (TX_MARGIN_DELAY / 1e6) <= started_time - (TX_START_DELAY + TX_JIT_DELAY) / 1e6):
                if give_collission:
                    return (True,existing_end)
                return True
        return False

    def TimeOnAir(self, payload_size_bytes, spreading_factor, bandwidth_khz=125, coding_rate=1, preamble_length=8, explicit_header=True, crc_enabled=True, low_dr_optimize='auto'):
        t_sym = (2 ** spreading_factor) / (bandwidth_khz * 1000) * 1000
        t_preamble = (preamble_length + 4.25) * t_sym
        h = 0 if explicit_header else 1
        if low_dr_optimize == 'auto':
            de = 1 if (bandwidth_khz == 125 and spreading_factor >= 11) else 0
        else:
            de = 1 if low_dr_optimize else 0
        cr = coding_rate + 4
        payload_symb_nb = 8 + max(
            math.ceil(
                (8 * payload_size_bytes - 4 * spreading_factor + 28 + (16 if crc_enabled else 0) - 20 * h) /
                (4 * (spreading_factor - 2 * de))
            ) * cr,
            0
        )
        t_payload = payload_symb_nb * t_sym
        return t_preamble + t_payload
    
    def check_duty_cycle(self, frame_to_schedule, gateway, Rx_Window,just_check=False):
        start_time_to_schedule = frame_to_schedule.sendTime
        time_on_air = frame_to_schedule.receivedTime - frame_to_schedule.sendTime
        if start_time_to_schedule > self.next_available_time[gateway.gateway_id][str(Rx_Window)]:
            if not just_check:
                if Rx_Window == 0:
                    time_blocked = 99 * time_on_air
                    #self.next_available_time[gateway.gateway_id][str(Rx_Window)] = frame_to_schedule.receivedTime + 99 * time_on_air
                elif Rx_Window == 1:
                    time_blocked = 9 * time_on_air
                
                self.next_available_time[gateway.gateway_id][str(Rx_Window)] = frame_to_schedule.receivedTime + time_blocked

                gateway.available_tx_time[Rx_Window + 1] -= time_on_air
                self.acumualted_blocked[(gateway.gateway_id, Rx_Window)] += time_blocked
            return True
        return False
    
    def check_duty_cycle_budget(self, frame_to_schedule, gateway, Rx_Window,just_check=False):

        time_on_air = frame_to_schedule.receivedTime - frame_to_schedule.sendTime

        # if float(frame_to_schedule.sendTime)/3600.0 > self.current_hour:
        #     self.current_hour +=1
        #     for gw in self.gateways.values():
        #         gw.reset_dc()
        #         print("Resetting duty cycle for all gateways at hour", self.current_hour-1)
        #         print("Gateway", gw.gateway_id, "Available TX Time Rx1:", gw.available_tx_time[1], "Available TX Time Rx2:", gw.available_tx_time[2])
        #     if not just_check:
        #         gateway.available_tx_time[Rx_Window + 1] -= time_on_air

        #     return True
    
        # Budget mode must ensure remaining budget can fully cover this packet.
        if gateway.available_tx_time[Rx_Window + 1] >= time_on_air:
            if not just_check:
                gateway.available_tx_time[Rx_Window + 1] -= time_on_air
            return True

        return False
    
    def update_reward_after_availability(self,gw_id,rx,dl_tempative,gateways,multi_position =1):
        blocked = self.check_duty_cycle(dl_tempative, gateways[gw_id], rx,True)
        conflict = self.check_conflicts(dl_tempative, gateways[gw_id])
        #print(self.StateOptions)
        if self.StateOptions[(gw_id, rx)] is not None:
            if not conflict and blocked and self.StateOptions[(gw_id, rx)][2]:
                # Pondarete the reward by the number of packet losses (higher losses reduce reward)
                loss_count = self.StateOptions[(gw_id, rx)][1]
                base_reward = self.StateOptions[(gw_id, rx)][0]
                #print("BASE REWARD for option for SF", (gw_id,rx), base_reward,self.StateOptions[(gw_id, rx)][3] )

                # Example: reward is scaled by 1/(1+loss_count), so more losses reduce reward
                #final_reward = base_reward/ (1 + loss_count)
                final_reward = base_reward
                #final_reward =  (1 / (1 + loss_count))
                #
                #print("FINAL REWARD for option for SF", (gw_id,rx),base_reward, final_reward,self.StateOptions[(gw_id, rx)][3] )
                self.StateOptions[(gw_id, rx)] = None
                self.Acumulated_rewards += final_reward
                self.rewards_history.append(final_reward)

                #print("ACUMULATED REWARD", )
                if self.rewards_history:
                    avg_reward = sum(self.rewards_history) / len(self.rewards_history)
                    #print("AVERAGE REWARD HISTORY:", avg_reward)
                return final_reward
        return None


