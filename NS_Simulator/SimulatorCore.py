from .NetworkServer import NetworkServer
from .TrafficGeneration import TrafficGeneration
from .PacketLogger import PacketLogger
from .Channel import Channel
import numpy as np
import random
import csv
import os
DEBUG = False
def debug_log(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


class SimulatorCore:
    def __init__(self, csv_path,scheduler,file_dump,Check_UL_GW=False, FullDuplex_GW=False,PL_selection="log"):
        self.Check_UL_GW = Check_UL_GW
        self.network_server = NetworkServer(scheduler)
        self.csv_path = file_dump
        self.traffic_gen = TrafficGeneration(csv_path, path_loss_selection=PL_selection)
        self.confirmed_uplink = []
        self.half_duplex_loss = []
        self.FullDuplex_GW = FullDuplex_GW
        self.failed_frames = []
        self.random = random.Random()
        self.random.seed(250)  # Set your desired seed value here
        self.logger = PacketLogger()
        self.sensitivity_map = {
            7: -124.0, 8: -127.0, 9: -130.0,
            10: -133.0, 11: -135.0, 12: -137.0
        }
        self.tx_rx = {1: 14, 2: 27}  # default tx power for rx1 and rx2
        debug_log("SimulatorCore initialized with network_server_cls:", self.network_server, "and traffic_gen_cls:", self.traffic_gen)

    def register_end_device_gateway(self):
        self.traffic_gen.ExtractTables()  # Extract tables from the CSV file
        debug_log("Registering end devices and gateways...")
        for device in self.traffic_gen.end_devices:
            debug_log("Registering end device:", device)
            self.network_server.register_end_device(device)
            self.logger.ed_sf[device.EndDeviceID] = device.SF  # Initialize scheduling results list for this device
            self.logger.SF_distribution[int(device.SF)].append(device)
            self.logger.num_ed += 1
        for gateway in self.traffic_gen.gateways:
            debug_log("Registering gateway:", gateway)
            
            self.network_server.register_gateway(gateway)

        self.network_server.init_scheduler()  # Initialize the scheduler with the registered gateways



    def get_rx_power_dbm(self, end_device, gateway, tx_power):
        distance = gateway.channel.get_distance((end_device.X, end_device.Y), (gateway.location[0], gateway.location[1]))
        debug_log(f"Calculating RX power: Distance between ED {end_device.EndDeviceID} and GW {gateway.gateway_id} is {distance:.2f} meters")
        rx_power =  gateway.channel.get_path_loss(self.random, distance,tx_power)
        debug_log(f"RX power at ED {end_device.EndDeviceID} from GW {gateway.gateway_id} is {rx_power:.2f} dBm")
        return rx_power

    def check_arrival_downlink(self, gateway_id, end_device_id, SF,downlink):

        end_device = self.network_server.end_devices[end_device_id]
        gateway = self.network_server.gateways[gateway_id]
        tx_power = downlink.power
        rx_power = self.get_rx_power_dbm(end_device, gateway, tx_power)
        if rx_power >= self.sensitivity_map[SF]:
            return True,rx_power
        else:
            return False,rx_power

    def simulate(self):
        debug_log("Starting simulation...")
        self.traffic_gen.TrafficRegister()
        for UL_frames in self.traffic_gen.frames:
            dl_frame = None
            failed = None
            rx_power = -1000000

            received_UL = []
            confirmed = self.network_server.is_confirmed(UL_frames)
            if confirmed:
                self.logger.add_packet_to("total_confirmed_UL", UL_frames[0])
                debug_log("Confirmed uplink frame:", UL_frames[0])

            for UL_frame in UL_frames:
                #print(self.network_server.gateways)
                rx_gw = self.network_server.gateways[UL_frame.receiverID]
                is_transmiting = rx_gw.check_transmiting_gateway(UL_frame)
                if is_transmiting and not self.FullDuplex_GW:

                    self.half_duplex_loss.append(UL_frame)
                    debug_log("Half-duplex loss for frame:", UL_frame)
                else:
                    received_UL.append(UL_frame)
                    
            if len(received_UL) <= 0:
                if confirmed:
                    self.logger.add_packet_to("Uplink_loss_half_duplex_confirmed",  UL_frames[0])
                else:
                    self.logger.add_packet_to("Uplink_loss_half_duplex_unconfirmed",  UL_frames[0])
            if len(received_UL)>0:
                debug_log("Processing frame:", received_UL[0])
                if confirmed:
                    self.logger.add_packet_to("transmited_confirmed_UL", received_UL[0])
                else:
                    self.logger.add_packet_to("transmited_unconfirm_UL", received_UL[0])

                dl_frame,failed,Reference_UL = self.network_server.receive_uplink(received_UL, confirmed)
                if dl_frame:
                    dl_frame.power = self.tx_rx[dl_frame.rx_window] #set the power for the downlink
                    debug_log("Downlink frame received:", dl_frame)
                    self.confirmed_uplink.append((Reference_UL, dl_frame))
                    self.logger.add_packet_to("transmited_DL", dl_frame)
                    received_gw = [frame.receiverID for frame in received_UL]
                    
                    if dl_frame.senderId in received_gw:
                        self.logger.add_packet_to("packetsScheduledReceivedGW", dl_frame)
                    received_by_ED,rx_power = self.check_arrival_downlink(dl_frame.senderId, dl_frame.receiverID, dl_frame.SF, dl_frame)
                    if received_by_ED:
                        self.network_server.Scheduler.ResultLastSchedule = True
                        self.logger.add_packet_to("downlinkReceivedByED", dl_frame)
                        debug_log("Downlink frame successfully received by end device:", dl_frame)
                        if received_UL[0].senderId not in self.logger.confirm_UL_schedul_U_n:
                            self.logger.confirm_UL_schedul_U_n[received_UL[0].senderId] = []
                        self.logger.confirm_UL_schedul_U_n[received_UL[0].senderId].append([1,0] if dl_frame.rx_window==1 else [0,1])
                    else:
                        self.network_server.Scheduler.ResultLastSchedule = False
                        if received_UL[0].senderId not in self.logger.confirm_UL_schedul_U_n:
                            self.logger.confirm_UL_schedul_U_n[received_UL[0].senderId] = []


                elif failed:
                    if received_UL[0].senderId not in self.logger.confirm_UL_schedul_U_n:
                        self.logger.confirm_UL_schedul_U_n[received_UL[0].senderId] = []

                    self.logger.confirm_UL_schedul_U_n[received_UL[0].senderId].append([0,0]) 
                    debug_log("Failed to schedule downlink for frames:", received_UL)
                    self.failed_frames.append((received_UL, failed))
                    self.logger.add_packet_to("DL_failure", failed)
                else:
                    debug_log("No downlink frame received for:", UL_frames[0])
                    if received_UL[0].senderId not in self.logger.confirm_UL_schedul_U_n:
                        self.logger.confirm_UL_schedul_U_n[received_UL[0].senderId] = []
                    self.logger.confirm_UL_schedul_U_n[received_UL[0].senderId].append([0,0]) 

            else:
                if UL_frames[0].senderId not in self.logger.confirm_UL_schedul_U_n:
                    self.logger.confirm_UL_schedul_U_n[UL_frames[0].senderId] = []
                self.logger.confirm_UL_schedul_U_n[UL_frames[0].senderId].append([0,0]) 
                random_moment = self.random.random()
                debug_log(f"Random moment for UL frames 1: {random_moment}")
                random_moment = self.random.random()
                debug_log(f"Random moment for UL frames 2: {random_moment}")
                random_moment = self.random.random()
                debug_log(f"Random moment for UL frames 3: {random_moment}")

            info = None
            if dl_frame:
                # Write downlink frame info with rx_power to CSV using add_packet_to
                info = {
                    "frame": dl_frame,
                    "rx_power": rx_power
                }
            elif failed:
                # Log schedule failure using add_packet_to
                info = {
                    "received_UL": received_UL,
                    "failure_reason": failed
                }
            elif len(received_UL) == 0 and confirmed:
                # Log as failure due to transmitting gateways
                info = {
                    "UL_frames": UL_frames,
                    "failure_reason": "No downlink scheduled due to transmitting gateways"
                }
            # Write info to CSV file
            # Define a fixed set of column names for all rows
            fieldnames = ["frame", "rx_power", "received_UL", "failure_reason", "UL_frames"]
            # Prepare row with all columns, fill missing with empty string
            row = {key: "" for key in fieldnames}
            if info and self.Check_UL_GW:
                for key in info:
                    row[key] = str(info[key])
                write_header = not os.path.exists(self.csv_path + ".csv")
                with open(self.csv_path + ".csv", mode='a', newline='') as file:
                    writer = csv.DictWriter(file, fieldnames=fieldnames)
                    if write_header:
                        writer.writeheader()
                    writer.writerow(row)
        debug_log("Simulation completed.")
        
        for rx in self.logger.consumed_duty_cycle:                
            rx_dc = []
            for gateway in self.network_server.gateways.values():
            
                rx_dc.append(gateway.available_tx_time[rx]) #capture the remaining duty cycle for each rx window on each gw 

            self.logger.consumed_duty_cycle[rx] = np.average(rx_dc)
        self.logger.final_reward = self.network_server.Scheduler.Acumulated_rewards
        self.logger.reward_history = self.network_server.Scheduler.rewards_history
        debug_log("Final accumulated reward:", self.logger.final_reward)

