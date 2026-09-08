import pandas as pd
from .EndDevice import EndDevice
from io import StringIO
from .Frame import Frame
from .LoRaGateway import LoRaGateway  # Assuming this class exists in your project
from .NetworkServer import NetworkServer
from collections import defaultdict
from .Channel import Channel
import random
import os

# Debug macro
DEBUG = False
WITH_COUNTER = True
def debug_log(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)

class TrafficGeneration:
    def __init__(self, csv_path = "",path_loss_selection="log"):
        self.csv_path = csv_path
        self.devices_table = None
        self.uplinks_table = None
        self.gateway_table = None
        self.gateway_table_new = None
        self.gateways = None
        self.end_devices = None
        self.snr_by_receiver = None
        self.frames = None
        self.seed = None
        self.path_loss_selection = path_loss_selection
        self.pos_gw_fix = {
            "1": [250.0, 0.0, 1.5],
            "2": [-250.0, 0.0, 1.5],
            "3": [0.0, 250.0, 1.5],
            "4": [0.0, -250.0, 1.5],
            "5": [250.0, 250.0, 1.5],
            "6": [-250.0, -250.0, 1.5]
        }
        # self.pos_gw_fix = {
        #     "1": [0.0, 0.0],
        #     "2": [0.0, 3723.91],
        #     "3": [-3225.0, 1861.95],
        #     "4": [-3225.0, -1861.95],
        #     "5": [-4.56047e-13, -3723.91],
        #     "6": [3225.0, -1861.95],
        #     "7": [3225.0, 1861.95],
        #     "8": [0.0, 7447.82],
        #     "9": [-3225.0, 5585.86],
        #     "10": [-6450.0, 3723.91]
        # }
        debug_log(f"Initializing TrafficGeneration with CSV: {csv_path}")

    def _extract_table_from_lines(self, header, lines):
        debug_log(f"Extracting table with header: {header}")
        start_idx = None
        for idx, line in enumerate(lines):
            if all(h in line for h in header):
                start_idx = idx
                break
        if start_idx is None:
            debug_log("Header not found in lines.")
            return None
        # Find end of table (either next header or end of lines)
        end_idx = len(lines)
        for idx in range(start_idx + 1, len(lines)):
            if any(h in lines[idx] for h in header):
                end_idx = idx
                break
        table_lines = lines[start_idx:end_idx]
        debug_log(f"Table lines extracted from {start_idx} to {end_idx}")
        return pd.read_csv(StringIO(''.join(table_lines)), sep=';')

    def _extract_table_with_headers(self,file_path, headers):
        debug_log(f"Reading file: {file_path}")
        # Extract seed number from filename
        filename = os.path.basename(file_path)
        if 'seed_' in filename:
            self.seed = filename.split('seed_')[1].split('_')[0]
        with open(file_path, 'r') as file:
            lines = file.readlines() 
        
        # Find the starting index of the table by matching headers
        for idx, line in enumerate(lines):
            if all(header in line for header in headers):
                start_idx = idx + 1
                break
        else:
            # If headers not found, return an empty DataFrame with the expected columns
            return pd.DataFrame(columns=headers)
        
        # Extract table lines
        table_lines = []
        for line in lines[start_idx:]:
            if line.strip() == "" or not line[0].isdigit():
                break
            table_lines.append(line.strip())
        
        # Create DataFrame
        data = [row.split(',') for row in table_lines]
        

        df = pd.DataFrame(data, columns=headers) 
        return df
        

    def ExtractTables(self):
        self.devices_table = None
        self.uplinks_table = None
        self.gateway_table = None
        self.gateways = None
        self.end_devices = None
        self.snr_by_receiver = None
        self.frames = None
        debug_log("Reading CSV file for tables...")
        #with open(self.csv_path, 'r') as f:
            #lines = f.readlines()

        gateway_header = ['gatewayID', 'Received', 'Interfered', 'No Receivers', ' Under', ' GW busy', ' unset'] #keep this just to make it compatible with other logs
        gateway_header_new = ['gatewayID', 'X', 'Y', 'Z', '']

        device_header = ['EndDeviceID', 'X', 'Y', 'Z', 'SF','']
        uplink_header = ['senderId', 'receiverID', ' sendTime', ' receivedTime', 'SF', 'SNR', 'Ftype', ' Freq', 'received', 'code','']
        uplink_header_with_counter = ['senderId', 'receiverID', ' sendTime', ' receivedTime', 'SF', 'SNR','RSSI', 'Ftype', ' Freq', 'n_frame', 'received', 'code','']

        if WITH_COUNTER:
            uplink_header = uplink_header_with_counter
        self.devices_table = self._extract_table_with_headers(self.csv_path,device_header)
        debug_log("Devices table extracted:", self.devices_table)


        self.uplinks_table = self._extract_table_with_headers(self.csv_path, uplink_header)
        
        debug_log("Uplinks table extracted:", self.uplinks_table)
        self.gateway_table = self._extract_table_with_headers(self.csv_path,gateway_header)
        debug_log("Gateway table extracted:", self.gateway_table)
        self.gateway_table_new = self._extract_table_with_headers(self.csv_path,gateway_header_new)
        debug_log("Gateway new table extracted:", self.gateway_table_new)
        # Convert columns to numeric types in uplinks_table
        numeric_cols = [' sendTime', ' receivedTime', 'SF', 'SNR', 'RSSI', 'Ftype', ' Freq']
        for col in numeric_cols:
            if col in self.uplinks_table.columns:
                self.uplinks_table[col] = pd.to_numeric(self.uplinks_table[col], errors='coerce')
        self.end_devices = self.RegisterED()
        self.frames = self.TrafficRegister()
        self.gateways = self.RegisterGateway()

    def RegisterGateway(self):
        debug_log("Registering gateways...")
        gateway_list = []
        table_to_use = self.gateway_table_new if not self.gateway_table_new.empty else self.gateway_table
        for _, row in table_to_use.iterrows():
            #debug_log(f"Registering gateway: {row}")
            channel = Channel(self.path_loss_selection,self.seed)  # Create a Channel instance (customize as needed)
            if self.gateway_table_new is not None and not self.gateway_table_new.empty:
                gateway = LoRaGateway(
                    gateway_id=row['gatewayID'],
                    channel=channel,
                    location=[float(row['X']), float(row['Y']), float(row['Z'])]
                )
            else:
                gateway = LoRaGateway(
                    gateway_id=row['gatewayID'],
                    channel=channel,
                    location=self.pos_gw_fix[row['gatewayID']]
                )
            gateway_list.append(gateway)

        if len(gateway_list) == 1:
            gateway_list[0].location = [0,0]
        debug_log(f"Total gateways registered: {len(gateway_list)}")
        return gateway_list
    
    def RegisterED(self):
        debug_log("Registering end devices...")
        ed_list = []
        #debug_log(f"Registering end device: {self.devices_table}")

        for _, row in self.devices_table.iterrows():
            ed = EndDevice(row["EndDeviceID"],float(row['X']),float(row['Y']),float(row['Z']),float(row['SF']))
            ed_list.append(ed)
        debug_log(f"Total end devices registered: {len(ed_list)}")
        return ed_list

    def TrafficRegister(self):
        debug_log("Registering traffic frames...")
        frame_list = []
        frame_number = 0
        added_frames = {}

        # Extract all SNR values for each receiverID
        self.snr_by_receiver = {}
        # Use groupby to collect SNR values for each receiverID efficiently
        self.snr_by_receiver = self.uplinks_table.groupby('receiverID')['SNR'].apply(lambda x: [snr for snr in x if snr != 0]).to_dict()
        
        for _, row in self.uplinks_table.iterrows():
            fcnt = 0
            if 'n_frame' in self.uplinks_table.columns:
                fcnt = int(row['n_frame'])
            frame = Frame(
                senderId=row['senderId'],
                receiverID=row['receiverID'],
                sendTime=row[' sendTime']/1e9,
                receivedTime=row[' receivedTime']/1e9,
                SF=row['SF'],
                SNR=row['SNR'],
                RSSI=row['RSSI'],  # Assuming RSSI is the same as SNR for now, adjust if needed
                Ftype=row['Ftype'],
                fcnt=fcnt,
                rx_or_tx='rx'
            )

            # If SNR is 0, replace it with a random value from the observed SNRs for this receiverID
            if row['SNR'] == 0 and row['receiverID'] in self.snr_by_receiver:
                valid_snrs = self.snr_by_receiver[row['receiverID']]
                if valid_snrs:
                    min_snr = min(valid_snrs)
                    max_snr = max(valid_snrs)
                    frame.SNR = random.uniform(min_snr, max_snr)
                    debug_log(f"Replaced SNR 0 with random value {frame.SNR} for receiverID {row['receiverID']}")
                if row['RSSI'] == 0 and row['receiverID'] in self.snr_by_receiver:
                    valid_rssis = self.snr_by_receiver[row['receiverID']]
                    if valid_rssis:
                        min_rssi = min(valid_rssis)
                        max_rssi = max(valid_rssis)
                        frame.RSSI = random.uniform(min_rssi, max_rssi)
                        debug_log(f"Replaced RSSI 0 with random value {frame.RSSI} for receiverID {row['receiverID']}")
            time_id = (row['senderId'], row[' sendTime'])
            if time_id in added_frames:
                #debug_log(f"Frame already exists for {time_id}, appending.")
                frame_list[added_frames[time_id]].append(frame)
            else:
                #debug_log(f"New frame for {time_id}, creating entry.")
                added_frames[time_id] = frame_number
                frame_list.append([frame])
                frame_number += 1

        debug_log("Sorting frame list by receivedTime...")
        frame_list.sort(key=lambda frames: frames[0].receivedTime if frames else float('inf'))
        debug_log("Traffic frames registered.")
        return frame_list
    
    def export_frames_to_csv(self, output_path):
        rows = []
        for frames in self.frames:
            for frame in frames:
                rows.append({
                    'senderId': frame.senderId,
                    'receiverID': frame.receiverID,
                    ' sendTime': frame.sendTime,
                    ' receivedTime': frame.receivedTime,
                    'SF': frame.SF,
                    'SNR': frame.SNR,
                    'Ftype': frame.Ftype
                })
        df = pd.DataFrame(rows, columns=['senderId', 'receiverID', ' sendTime', ' receivedTime', 'SF', 'SNR', 'Ftype'])
        df.to_csv(output_path, index=False)