import csv
import numpy as np
class PacketLogger:
    def __init__(self):
        self.total_confirmed_UL = []
        self.transmited_confirmed_UL = [] #This are actually the received ones discounting the half-duplex losses
        self.transmited_unconfirm_UL = []#This are actually the received ones discounting the half-duplex losses
        self.transmited_DL = []
        self.DL_failure = []
        self.confirm_UL_schedul_U_n = {}
        self.packetsScheduledReceivedGW = []
        self.downlinkReceivedByED = []
        self.default_SF_Rx2 = 12
        self.Uplink_loss_half_duplex_confirmed = []
        self.Uplink_loss_half_duplex_unconfirmed = []
        self.ed_sf = {}
        self.num_ed = 0
        self.final_reward = 0
        self.reward_history = []
        self.SF_distribution = {7: [], 8: [], 9: [], 10: [], 11: [], 12: []}
        self.time_window_size = 3600  # 30 minutes in seconds

        self.consumed_duty_cycle = { # here is the consumed duty cycle at the end of the simulation for each rx window and for each gateway. 
            1: 0,  
            2: 0
        }
        self.duty_cycle_results = {}

    def add_packet_to(self, category, packet):

        if category == "transmited_confirmed_UL":
            self.transmited_confirmed_UL.append(packet)
        elif category == "packetsScheduledReceivedGW":
            self.packetsScheduledReceivedGW.append(packet)
        elif category == "downlinkReceivedByED":
            self.downlinkReceivedByED.append(packet)
        elif category == "total_confirmed_UL":
            self.total_confirmed_UL.append(packet)
        elif category == "transmited_unconfirm_UL":
            self.transmited_unconfirm_UL.append(packet)
        elif category == "transmited_DL":
            self.transmited_DL.append(packet)
        elif category == "DL_failure":
            self.DL_failure.append(packet)
        elif category == "Uplink_loss_half_duplex_confirmed":
            self.Uplink_loss_half_duplex_confirmed.append(packet)

        elif category == "Uplink_loss_half_duplex_unconfirmed":
            self.Uplink_loss_half_duplex_unconfirmed.append(packet)    
        else:
            raise ValueError(f"Unknown category: {category}")


    def export_transmited_DL_to_csv(self, filename):

        # Define the header as specified
        header = ["senderId", "receiverID", "sendTime", "receivedTime", "SF", "SNR", "Ftype", "Freq", "RX"]

        with open(filename, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(header)
            for packet in self.transmited_DL:
                # Assumes each packet is a dict with the required keys
                row = [
                    getattr(packet, "senderId", ""),
                    getattr(packet, "receiverID", ""),
                    getattr(packet, "sendTime", ""),
                    getattr(packet, "receivedTime", ""),
                    getattr(packet, "SF", ""),
                    getattr(packet, "SNR", ""),
                    getattr(packet, "Ftype", ""),
                    getattr(packet, "Freq", ""),
                    getattr(packet, "rx_window", "")
                ]
                writer.writerow(row)

    def _compute_sf_ack(self, sf, den, div, Ul_div=True):
        """Compute the ACK percentage for a specific SF."""
        if Ul_div: conf_sf = [x for x in div if x.SF == sf]
        else: conf_sf = [x for x in div if x.original_SF == sf]
        DL_sf = [x for x in den if x.original_SF == sf]
        return len(DL_sf) / (conf_sf and len(conf_sf) or 1)  # Avoid division by zero
    
    def _compute_duty_cycle_consumption(self):
        gateway_dc = {}
        for packet in self.transmited_DL:
            g = packet.senderId
            
            ToA = packet.receivedTime - packet.sendTime
            if g not in gateway_dc:
                gateway_dc[g] = {'RX1': 0.0, 'RX2': 0.0, 'RX1_timeline': [], 'RX2_timeline': []}
            if packet.rx_window == 1:
                gateway_dc[g]['RX1'] += ToA
                
            elif packet.rx_window == 2:
                gateway_dc[g]['RX2'] += ToA
                
            gateway_dc[g]['RX1_timeline'].append((packet.sendTime, gateway_dc[g]['RX1']))
            gateway_dc[g]['RX2_timeline'].append((packet.sendTime, gateway_dc[g]['RX2']))
                
            # Clean up and store results
        for g, dc_data in gateway_dc.items():
            if g not in self.duty_cycle_results:
                self.duty_cycle_results[g] = {}
            
            # Remove duplicates and keep unique time points
            rx1_timeline = []
            rx2_timeline = []
            prev_rx1_dc = -1
            prev_rx2_dc = -1
            
            for (time, rx1_dc), (_, rx2_dc) in zip(dc_data['RX1_timeline'], dc_data['RX2_timeline']):
                if rx1_dc != prev_rx1_dc:
                    rx1_timeline.append((time, rx1_dc))
                    prev_rx1_dc = rx1_dc
                if rx2_dc != prev_rx2_dc:
                    rx2_timeline.append((time, rx2_dc))
                    prev_rx2_dc = rx2_dc
            
            self.duty_cycle_results[g] = {
                'RX1': rx1_timeline,
                'RX2': rx2_timeline
            }
        return self.duty_cycle_results
    
    
    def _compute_rx_per_sf_ack(self, sf):
        """Compute the ACK percentage for a specific SF."""

        conf_sf = [x for x in self.total_confirmed_UL if x.SF == sf]
        DL_sf = [x for x in self.transmited_DL if x.original_SF == sf]
        return len(DL_sf) / (conf_sf and len(conf_sf) or 1)  # Avoid division by zero
    def _compute_rx_per_sf_ack(self, sf, rx):
        """Compute the ACK percentage for a specific SF."""

        conf_sf = [x for x in self.transmited_DL if x.original_SF == sf]
        DL_sf = [x for x in self.transmited_DL if x.original_SF == sf and x.rx_window == rx]
        return len(DL_sf) / (conf_sf and len(conf_sf) or 1)  # Avoid division by zero
    
    def compute_statistics_per_seconds_window(self):

            endTime = self.total_confirmed_UL[-1].receivedTime if len(self.total_confirmed_UL) > 0 else 0
            aproximate_num_windows = int(endTime / self.time_window_size) + 1
            stats_per_hour = {}
            for i in range(aproximate_num_windows):
                start_window = i * self.time_window_size
                end_window = (i + 1) * self.time_window_size

                window_confirmed_UL = [pkt for pkt in self.total_confirmed_UL if start_window <= pkt.receivedTime < end_window]
                window_transmited_DL = [pkt for pkt in self.transmited_DL if start_window <= pkt.receivedTime < end_window]
                window_received_by_ED = [pkt for pkt in self.downlinkReceivedByED if start_window <= pkt.receivedTime < end_window]

                stats = {
                    "ACK%": len(window_transmited_DL)/ (len(window_confirmed_UL)) if len(window_confirmed_UL) > 0 else 0,
                    "downlinkReceivedByED": len(window_received_by_ED)/len(window_transmited_DL) if len(window_transmited_DL) > 0 else 0,
                    "CPSR": len(window_received_by_ED)/len(window_confirmed_UL) if len(window_confirmed_UL) > 0 else 0,
                }
                
                stats_per_hour[f"Hour_{i}"] = stats
            return stats_per_hour
    
    def _jains_index_computation(self):
        acks = []
        for ed in self.confirm_UL_schedul_U_n:
                
            ed_ack = sum(1 for result in self.confirm_UL_schedul_U_n[ed] if result == [1,0] or result == [0,1])/len(self.confirm_UL_schedul_U_n[ed]) if len(self.confirm_UL_schedul_U_n[ed]) > 0 else 0
            acks.append(ed_ack)
            
   
        
        #print("Average energy consumption per end device (mA):", np.average(energy_total))
        jains_index = (sum(acks) ** 2) / (len(acks) * sum(x ** 2 for x in acks)) if len(acks) > 0 and sum(x ** 2 for x in acks) > 0 else 0

        return jains_index
    def _compute_energy_consumption_per_ed(self):
        Trx1w = [991.8, 577.5, 288.7, 144.4, 72.2, 41.2]
        time =                    [169.2, 80.4, Trx1w, 988.4, Trx1w, 337, 991.8, 337.8, 272.5, 37.5]
        #                          4.    5     6      7      8      9      10     11
        energy_consumed_no_ack  = [22.1, 13.7, 82.8  ,27.0, 38.1, 27.1,  5.0,  13.2,  21.0,  13.3]
        energy_consumed_ack_rx1 = [22.1, 13.7, 82.8  ,27.1, 31.8, 0,     0,    13.4,  20.9,  13.4]
        energy_consumed_ack_rx2 = [22.1, 13.7, 82.8  ,27.0, 38.1, 27.1,  38.0, 13.4,  21.0,  13.3]     
        energy_total = []
        total_batery_consumption_per_ed = []
        for ed in self.confirm_UL_schedul_U_n:
            # Assuming each packet has an attribute 'energy_consumed'
            ed_energy = 0
            end_device_energy = []
            total_time = 0
            I_mh = 0
            for result in self.confirm_UL_schedul_U_n[ed]:
                if result == [0,0]:  # No ACK received
                    ed_energy = energy_consumed_no_ack
                elif result == [1,0]:  # ACK received in RX1
                    ed_energy = energy_consumed_ack_rx1
                elif result == [0,1]:  # ACK received in RX2
                    ed_energy = energy_consumed_ack_rx2
                
                for step in range(len(ed_energy)):
                    if step ==2 or step == 4:
                        trx1_ed = Trx1w[12-int(self.ed_sf[ed])]
                        I_mh += ed_energy[step] * trx1_ed/(3.6e6)  # Convert to mAh
                        total_time += trx1_ed
                    else:   
                        I_mh += ed_energy[step] * time[step]/(3.6e6)  # Convert to mAh
                        total_time += time[step]
            
            #print(f"ED {ed} - Total Energy Consumption: {I_mh:.6f} mAh, Total Time: {total_time/1000:.2f} seconds")
       
            I_mh+=(45e-3)*(3600-total_time/1000)/3600 # Add sleep consumption assuming 45mA in sleep and the rest of the time until 1 hour is sleeping
            ed_consumption_1_hour = (10000/I_mh)/(24*365) if I_mh > 0 else 0  # Convert to mAh assuming a 1A battery for 1 hour
            total_batery_consumption_per_ed.append(ed_consumption_1_hour)  # Convert to mAh assuming a 1A battery for 1 hour
        energy_total= np.average(total_batery_consumption_per_ed)
        
        #print("Average energy consumption per end device (mA):", np.average(energy_total))
        
        return energy_total
    def compute_statistics(self):

        avg_reward = sum(self.reward_history) / len(self.reward_history) if len(self.reward_history) > 0 else 0
        stats = {
            "ACK%": len(self.transmited_DL)/ (len(self.total_confirmed_UL)) if len(self.total_confirmed_UL) > 0 else 0,
            "duty_cycle_Rx1_left": self.consumed_duty_cycle[1]/36,
            "duty_cycle_Rx2_left": self.consumed_duty_cycle[2]/360,
            "packetsScheduledReceivedGW": len(self.packetsScheduledReceivedGW)/len(self.transmited_DL) if len(self.transmited_DL) > 0 else 0,
            "downlinkReceivedByED": len(self.downlinkReceivedByED)/len(self.transmited_DL) if len(self.transmited_DL) > 0 else 0,
            "CPSR": len(self.downlinkReceivedByED)/len(self.total_confirmed_UL) if len(self.total_confirmed_UL) > 0 else 0,
            "Final_Reward": self.final_reward,
            "average_reward": avg_reward,
            "Jains_index": self._jains_index_computation(),
            "used_rx1_percentage": sum(1 for pkt in self.downlinkReceivedByED if pkt.rx_window == 1) / len(self.total_confirmed_UL) if len(self.total_confirmed_UL) > 0 else 0,
            "used_rx2_percentage": sum(1 for pkt in self.downlinkReceivedByED if pkt.rx_window == 2) / len(self.total_confirmed_UL) if len(self.total_confirmed_UL) > 0 else 0,
            "used_rx1_percentage_total": sum(1 for pkt in self.downlinkReceivedByED if pkt.rx_window == 1) / len(self.downlinkReceivedByED) if len(self.downlinkReceivedByED) > 0 else 0,
            "used_rx2_percentage_total": sum(1 for pkt in self.downlinkReceivedByED if pkt.rx_window == 2) / len(self.downlinkReceivedByED) if len(self.downlinkReceivedByED) > 0 else 0,
            "duty_cycle_monitoring": self._compute_duty_cycle_consumption(),
            "Energy_Consumption_average_ed": self._compute_energy_consumption_per_ed(),
            "ACK_sf7": self._compute_sf_ack(7,self.transmited_DL,self.total_confirmed_UL),
            "ACK_sf8": self._compute_sf_ack(8,self.transmited_DL,self.total_confirmed_UL),
            "ACK_sf9": self._compute_sf_ack(9,self.transmited_DL,self.total_confirmed_UL),
            "ACK_sf10": self._compute_sf_ack(10,self.transmited_DL,self.total_confirmed_UL),
            "ACK_sf11": self._compute_sf_ack(11,self.transmited_DL,self.total_confirmed_UL),
            "ACK_sf12": self._compute_sf_ack(12,self.transmited_DL,self.total_confirmed_UL),
            "DL_PDR_sf7": self._compute_sf_ack(7,self.downlinkReceivedByED,self.transmited_DL,False),
            "DL_PDR_sf8": self._compute_sf_ack(8,self.downlinkReceivedByED,self.transmited_DL,False),
            "DL_PDR_sf9": self._compute_sf_ack(9,self.downlinkReceivedByED,self.transmited_DL,False),
            "DL_PDR_sf10": self._compute_sf_ack(10,self.downlinkReceivedByED,self.transmited_DL,False),
            "DL_PDR_sf11": self._compute_sf_ack(11,self.downlinkReceivedByED,self.transmited_DL,False),
            "DL_PDR_sf12": self._compute_sf_ack(12,self.downlinkReceivedByED,self.transmited_DL,False),
            "DL_PDR_total_sf7": self._compute_sf_ack(7,self.downlinkReceivedByED,self.total_confirmed_UL),
            "DL_PDR_total_sf8": self._compute_sf_ack(8,self.downlinkReceivedByED,self.total_confirmed_UL),
            "DL_PDR_total_sf9": self._compute_sf_ack(9,self.downlinkReceivedByED,self.total_confirmed_UL),
            "DL_PDR_total_sf10": self._compute_sf_ack(10,self.downlinkReceivedByED,self.total_confirmed_UL),
            "DL_PDR_total_sf11": self._compute_sf_ack(11,self.downlinkReceivedByED,self.total_confirmed_UL),
            "DL_PDR_total_sf12": self._compute_sf_ack(12,self.downlinkReceivedByED,self.total_confirmed_UL),
            "SF_COUNT_sf7": len(self.SF_distribution[7])/self.num_ed if self.num_ed > 0 else 0,
            "SF_COUNT_sf8": len(self.SF_distribution[8])/self.num_ed if self.num_ed > 0 else 0,
            "SF_COUNT_sf9": len(self.SF_distribution[9])/self.num_ed if self.num_ed > 0 else 0,
            "SF_COUNT_sf10": len(self.SF_distribution[10])/self.num_ed if self.num_ed > 0 else 0,
            "SF_COUNT_sf11": len(self.SF_distribution[11])/self.num_ed if self.num_ed > 0 else 0,
            "SF_COUNT_sf12": len(self.SF_distribution[12])/self.num_ed if self.num_ed > 0 else 0,
            "USE_Rx1_sf7": self._compute_rx_per_sf_ack(7,1),
            "USE_Rx1_sf8": self._compute_rx_per_sf_ack(8,1),
            "USE_Rx1_sf9": self._compute_rx_per_sf_ack(9,1),
            "USE_Rx1_sf10": self._compute_rx_per_sf_ack(10,1),
            "USE_Rx1_sf11": self._compute_rx_per_sf_ack(11,1),
            "USE_Rx1_sf12": self._compute_rx_per_sf_ack(12,1),
            "USE_Rx2_sf7": self._compute_rx_per_sf_ack(7,2),
            "USE_Rx2_sf8": self._compute_rx_per_sf_ack(8,2),
            "USE_Rx2_sf9": self._compute_rx_per_sf_ack(9,2),
            "USE_Rx2_sf10": self._compute_rx_per_sf_ack(10,2),
            "USE_Rx2_sf11": self._compute_rx_per_sf_ack(11,2),
            "USE_Rx2_sf12": self._compute_rx_per_sf_ack(12,2),
            "Loss_half_duplex%": len(self.Uplink_loss_half_duplex_confirmed)/ (len(self.total_confirmed_UL)) if len(self.total_confirmed_UL) > 0 else 0
        }
        return stats


    def dl_failure_report(self):
        blocked_count = 0
        conflict_count = 0
        mix_count = 0

        for failed in self.DL_failure:
            for gateway in failed:
                for rx in failed[gateway]:
                    reasons = failed[gateway][rx]
                    blocked = reasons.get('blocked_f', False)
                    conflict = reasons.get('conflict_f', False)
                    if blocked and conflict:
                        mix_count += 1
                    elif blocked:
                        blocked_count += 1
                    elif conflict:
                        conflict_count += 1

        return {
            "blocked": blocked_count,
            "conflict": conflict_count,
            "mix": mix_count
        }
    def __str__(self):
        report = {
            "transmited_confirmed_UL": len(self.transmited_confirmed_UL),
            "transmited_unconfirm_UL": len(self.transmited_unconfirm_UL),
            "transmited_DL": len(self.transmited_DL),
            "DL_failure": len(self.DL_failure),
            "Uplink_loss_half_duplex_confirmed": len(self.Uplink_loss_half_duplex_confirmed),
            "Uplink_loss_half_duplex_unconfirmed": len(self.Uplink_loss_half_duplex_unconfirmed)
        }
        return str(report)