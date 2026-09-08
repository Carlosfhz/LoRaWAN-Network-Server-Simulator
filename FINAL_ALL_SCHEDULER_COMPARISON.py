"""Run and compare the network-server scheduling algorithms.

This is the main experiment launcher for the project. It can either load
previously generated analysis data or run the heuristic schedulers and the
global optimization scheduler over every selected uplink-log directory.

Run this file from the repository root so that the ``NS_Simulator`` and
``Schedulers`` packages can be imported correctly::

    python FINAL_ALL_SCHEDULER_COMPARISON.py
"""

import datetime
import matplotlib.pyplot as plt
import glob
import json
import os
import re
import matplotlib.pyplot as plt
# Core simulator components. These classes parse the input logs, simulate
# uplinks/downlinks, and collect the metrics used in the final comparison.
from NS_Simulator.NetworkServer import NetworkServer
from NS_Simulator.SimulatorCore import SimulatorCore
from NS_Simulator.DataAnalysis import DataAnalysis
from NS_Simulator.TrafficGeneration import TrafficGeneration

# Scheduler implementations. Every scheduler receives the same simulator
# input and is evaluated through the same SimulatorCore workflow.
from Schedulers.GreedyFuture import GreedyFuture
from Schedulers.SchedulerBudgetGreedyEntropy_RSSI_v2 import SchedulerBudgetGreedyEntropy_RSSI_v2
from Schedulers.SchedulerTraditional import SchedulerTraditional
from Schedulers.TraditionalThreshold import TraditionalThreshold
from Schedulers.OptimalSchedulling import OptimalSchedulling
from Schedulers.DutyCyleControl import DutyCyleControl
from Schedulers.GreedyFuture_Rolling_Horizon_complete_v3 import GreedyFuture_Rolling_Horizon_complete_v3


# Global experiment configuration.
FULLDUPLEX = False  # False models gateway half-duplex operation.
MODEL = "okumara"  # Path-loss model passed to TrafficGeneration/Channel.
DUTY_CYCLE = "blocked"  # Descriptive default; main() selects the active mode.
OUTPUT_IMAGES = "OUTPUT_IMAGES"  # Directory where DataAnalysis writes figures.
EXTRA = "COMPLETE_COMPARISON_ALL_WITH_SHILMPS_AGAIN"  # Output-name suffix.
CONSIDER_OPTIMAL = True  # Include the global optimization scheduler.
IMPORT_DATAANLAYSIS = True  # Load cached analysis instead of rerunning heuristics.
STORED_FOLDER = "Logs-Test"  # Parent directory containing input-log folders.

# Display names used as keys in DataAnalysis.OutputTable and in plot legends.
SCHEDULER_NAMES = {
    "scheduler_1": "WSBS",  # Replace with desired scheduler name
    "scheduler_2": "IABS",  # Replace with desired scheduler name
    "scheduler_3": "SHBS",  # Replace with desired scheduler name
    "scheduler_4": "DCBS",  # Replace with desired scheduler name
    "scheduler_5": "TTS",  # Replace with desired scheduler name
    "scheduler_6": "SFTS",  # Replace with desired scheduler name
    "scheduler_7": "Optimal"  # Replace with desired scheduler name
}

# Each item is a subdirectory under STORED_FOLDER. Change this list to select
# the experiments to process. Keeping one small folder here is useful for a
# quick test before launching the complete comparison.
carpets = ["10_REPETITIONS_CLOSE_END","10_REPETITIONS_FAR_AWAY","10_REPETITIONS-RANDOM-DISTRIBUTION-AREA"]
#carpets = ["10_REPETITIONS_FAR_AWAY"]
#carpets = ["10_REPETITION_PERIODIC_TRAFFIC"]
#carpets = ["10_REPETITIONS_OKUMARA_LIMITED_400_ED_2hours"]
#carpets = ["10_REPETITIONS_FAR_AWAY"]
#carpets = ["1_REPETITION_FAR_AWAY"]
#carpets = ["10_REPETITIONS-RANDOM-DISTRIBUTION-AREA"]
#carpets = ["1_REPETITION_OKUMARA_RANDOM_FULL"]   
#carpets = ["1_REPETITION_OKUMARA_RANDOM_FULL"]
#carpets = ["10_REPETITIONS_OKAMURA_800_ED_MULTI_GW_RANDOM"]
def extract_parameters(filename):
    """Extract scenario parameters encoded in an uplink-log filename.

    The returned tuple is ordered as ``(end_devices, gateways, percentage,
    period)`` because this is the key format expected by DataAnalysis.
    """
    # Input filenames encode the experiment metadata after ``period_`` and
    # before the final ``_log_uplinks.csv`` suffix.
    pattern = r"period_(\d+)_gateway_(\d+)_seed_\d+_percentage_(\d+)_log_N_ED_(\d+)_log_uplinks\.csv"
    match = re.search(pattern, os.path.basename(filename))
    if match:
        t = int(match.group(1))
        gw = int(match.group(2))
        p = int(match.group(3))
        n = int(match.group(4))
        print(f"Extracted parameters - period: {t}, gateways: {gw}, percentage: {p}, end devices: {n}")
        return (n, gw, p, t)  # Return as a tuple
    else:
        print("Filename does not match expected pattern.")
        return None
def main():
    """Run the selected experiments and generate comparison plots."""
    # The outer loops allow the same experiment code to be reused for several
    # duty-cycle modes and several input datasets.
    for duty_cycle_management in ["budget"]:
        for uplinks_dir in carpets:
            # Build paths relative to the repository root. The optimal result
            # cache is kept separate for each dataset and duty-cycle mode.
            path = f"{STORED_FOLDER}/{uplinks_dir}"
            results_file = f"RESULTS_OPTIMAL_{uplinks_dir}_{duty_cycle_management}.json"
            colors_TTS_CUS_OP = ['orange', 'seagreen', 'salmon', '#B07AA1','#76B7B2','#4E79A7','#E15759']
            uplinks_files = glob.glob(os.path.join(path, "*_uplinks.csv"))
            # DataAnalysis stores metrics by scheduler and scenario and later
            # turns those tables into plots.
            dataAnalysis = DataAnalysis(OUTPUT_IMAGES,uplinks_dir+f"_{duty_cycle_management}_{EXTRA}")

            # These values describe the nominal RX1/RX2 duty-cycle limits used
            # by scheduler constructors; the actual scheduling logic enforces
            # the selected mode.
            resources = {
                    'Rx1_duty_cycle': 1,  # Example duty cycle for Rx1
                    'Rx2_duty_cycle': 10   # Example duty cycle for Rx2v
                }
            Counter = 0

            # Cached analysis contains the heuristic results and plot metadata.
            # When it is available, the expensive heuristic simulations are
            # skipped and only the optimal results are loaded or computed.
            if IMPORT_DATAANLAYSIS:

                input_file = f"dataAnalysis_{uplinks_dir}_{duty_cycle_management}_{EXTRA}.json"
                if os.path.exists(input_file):
                    with open(input_file, 'r') as f:
                        data = json.load(f)
                        
                        dataAnalysis.directory = data.get("output_directory", dataAnalysis.directory)
                        print(f"DataAnalysis directory set to: {dataAnalysis.directory}")
                        dataAnalysis.name_figures = data.get("name_figures", dataAnalysis.name_figures)
                        print(f"DataAnalysis name_figures set to: {dataAnalysis.name_figures}")
                        dataAnalysis.color = data.get("colors", dataAnalysis.color)
                        dataAnalysis.color["scheduler_1"] = '#4E79A7'      # Tableau blue
                        dataAnalysis.color["scheduler_3"] = '#E15759'  # Tableau red
                        dataAnalysis.color["scheduler_2"] = '#B07AA1'    # Tableau purple
                        dataAnalysis.color["scheduler_4"] = '#76B7B2'     # Tableau cyan
                        
                        dataAnalysis.OutputTable = convert_keys_from_str(data.get("output_table", dataAnalysis.OutputTable))
                        
                        # Older JSON files may use previous scheduler names.
                        # Normalize them so old results remain comparable with
                        # the names configured above.
                        old_to_new_names = {
                            "WSS": SCHEDULER_NAMES["scheduler_1"],
                            SCHEDULER_NAMES["scheduler_3"]: SCHEDULER_NAMES["scheduler_2"],
                            SCHEDULER_NAMES["scheduler_2"]: SCHEDULER_NAMES["scheduler_3"],
                            "LDCS": SCHEDULER_NAMES["scheduler_4"],
                            "TTS": SCHEDULER_NAMES["scheduler_5"],
                            "SFTS": SCHEDULER_NAMES["scheduler_6"],
                            "Optimal": SCHEDULER_NAMES["scheduler_7"]
                        }
                        for old_name, new_name in old_to_new_names.items():
                            if old_name in dataAnalysis.OutputTable:
                                dataAnalysis.OutputTable[new_name] = dataAnalysis.OutputTable.pop(old_name)
                                if old_name in dataAnalysis.color:
                                    dataAnalysis.color[new_name] = dataAnalysis.color.pop(old_name)
                    print(f"DataAnalysis loaded from {input_file}")
                # Remove stale optimal data when the current run explicitly
                # excludes the optimizer.
                if not CONSIDER_OPTIMAL:
                    for scheduler_name in list(dataAnalysis.OutputTable.keys()):
                        if isinstance(scheduler_name, str) and scheduler_name.strip().lower() == "Optimal":
                            dataAnalysis.OutputTable.pop(scheduler_name, None)
                            dataAnalysis.color.pop(scheduler_name, None)
                else:
                    print(f"Input file {input_file} not found. Cannot import DataAnalysis.")


            

            # Run all heuristic schedulers only when cached analysis is not
            # being imported. Every scheduler uses the same input file and
            # contributes one row of metrics to DataAnalysis.
            for file in uplinks_files:
                if not IMPORT_DATAANLAYSIS:
                    print(f"Computing Traditional Processing file: {file}")
                    param= extract_parameters(file)
                    
                    # WSBS: entropy/RSSI-based budget scheduler.
                    schedul_name = SCHEDULER_NAMES["scheduler_1"]
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {schedul_name} file: {Counter}")
                    scheduler = SchedulerBudgetGreedyEntropy_RSSI_v2("ARMED", resources, duty_cycle_management, False)
                    Simulator = SimulatorCore(file, scheduler, "dump/INFO_"+schedul_name+str(param),False,False,MODEL)
                    Simulator.register_end_device_gateway()
                    Simulator.simulate()
                    dataAnalysis.add_data_outputTable(schedul_name, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[5])

                    # SHBS: future-aware greedy scheduler.
                    schedul_name = SCHEDULER_NAMES["scheduler_2"]    
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {schedul_name} file: {Counter}")

                    file_name = f"debug_log_{schedul_name}_{param}.txt"
                    scheduler = GreedyFuture("ARMED", resources, duty_cycle_management, False, file_name,10)
                    Simulator = SimulatorCore(file, scheduler, "dump/INFO_" + schedul_name + str(param),False,False,MODEL)
                    Simulator.register_end_device_gateway()
                    Simulator.simulate()
                    dataAnalysis.add_data_outputTable(schedul_name, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[3])

                    # IABS: rolling-horizon scheduler with a local optimizer.
                    schedul_name = SCHEDULER_NAMES["scheduler_3"]
                    file_name = f"debug_log_{schedul_name}_{param}.txt"  
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {schedul_name} file: {Counter}")

                    scheduler = GreedyFuture_Rolling_Horizon_complete_v3("ARMED", resources, duty_cycle_management, False, file_name,5)
                    #scheduler = SuperVise_expert("ARMED", resources, "blocked", False, file_name,5)
                    Simulator = SimulatorCore(file, scheduler, "dump/INFO_" + schedul_name + str(param),False,False,MODEL)
                    Simulator.register_end_device_gateway()
                    Simulator.simulate()
                    dataAnalysis.add_data_outputTable(schedul_name, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[6])
                    # per_hour_uplinks = Simulator.logger.compute_statistics_per_seconds_window()
                    # for hour, stats in per_hour_uplinks.items():
                    #     dataAnalysis_b.add_data_outputTable(f"{SchedulerTS}_hour_{hour}", param, stats)
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Q Learning TS file: {file}")


                    # DCBS: scheduler focused on duty-cycle control.
                    schedul_name = SCHEDULER_NAMES["scheduler_4"]
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Computing {schedul_name} Processing file: {Counter}")

                    scheduler = DutyCyleControl("TRADITIONAL", resources, duty_cycle_management,False,schedul_name+str(param))
                    # Create a new instance of SimulatorCore with the scheduler
                    Simulator = SimulatorCore(file,scheduler,"dump/INFO_"+schedul_name+str(param),False, FULLDUPLEX,MODEL)
                    # Register end devices and gateways
                    Simulator.register_end_device_gateway()
                    Simulator.simulate()
                    dataAnalysis.add_data_outputTable(schedul_name, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[4])

                


                    # TTS: traditional scheduler.
                    print(f"Computing Traditional Processing file: {file}")
                    schedul_name = SCHEDULER_NAMES["scheduler_5"]
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Computing {schedul_name} Processing file: {Counter}")

                    scheduler = SchedulerTraditional("TRADITIONAL", resources, duty_cycle_management)
                    # Create a new instance of SimulatorCore with the scheduler
                    Simulator = SimulatorCore(file,scheduler,"dump/INFO_"+schedul_name+str(param),False, FULLDUPLEX,MODEL)

                    # Register end devices and gateways
                    Simulator.register_end_device_gateway()

                    # Simulate the network
                    param= extract_parameters(file)

                    Simulator.simulate()

                    dataAnalysis.add_data_outputTable(schedul_name, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[0])
                    Counter +=1

                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Completed {Counter}/{len(uplinks_files)} files")
                    # SFTS: threshold-based traditional scheduler.
                    schedul_name = SCHEDULER_NAMES["scheduler_6"]
                    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Computing {schedul_name} Processing file: {Counter}")

                    scheduler = TraditionalThreshold("TRADITIONAL", resources, 9, duty_cycle_management)
                    Simulator = SimulatorCore(file, scheduler,"dump/INFO_"+schedul_name+str(param),False, FULLDUPLEX,MODEL)
                    # Register end devices and gateways
                    Simulator.register_end_device_gateway()
                    # Simulate the network
                    Simulator.simulate()
                    dataAnalysis.add_data_outputTable(schedul_name, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[1])

                    
            # The global optimizer is handled separately because it reads the
            # complete input directory and returns aggregate scenario results.
            # Its JSON cache prevents repeating expensive MILP solves.
            if CONSIDER_OPTIMAL:
                if os.path.exists(results_file):
                #if False:  # Force re-computation of optimal scheduling for fresh results, set to True to enable loading from file
                    print(f"Loading existing results from {results_file}")
                    with open(results_file, 'r') as f:
                        data = json.load(f)
                        stats_1 = data.get("stats", {})
                else:
                    
                    print(f"Results file not found. Running OptimalSchedulling...")
                    opT_1 = OptimalSchedulling(path,duty_cycle_management)
                    ALL_results, dc_results_1, stats_1 = opT_1.run()
                    
                    if ALL_results and stats_1:
                        stats_str_keys = convert_keys_to_str(stats_1)
                        # Create directory if it doesn't exist
                        results_dir = os.path.dirname(results_file)
                        if results_dir and not os.path.exists(results_dir):
                            os.makedirs(results_dir)
                        with open(results_file, 'w') as f:
                            json.dump({
                                "uplinks_dir": path,
                                "stats": stats_str_keys
                            }, f, indent=2, default=str)

                for param_key in stats_1:
                    param = tuple(map(int, param_key.strip('()').split(', '))) if isinstance(param_key, str) else param_key
                    for stats in stats_1[param_key]:
                        dataAnalysis.add_data_outputTable("Optimal", param, stats, colors_TTS_CUS_OP[2])



                    

            # Save the complete analysis table only when this run performed the
            # heuristic simulations. Imported analysis is already persisted.
            if not IMPORT_DATAANLAYSIS:
                output_file = f"dataAnalysis_{uplinks_dir}_{duty_cycle_management}_{EXTRA}.json"
                # Create directory if it doesn't exist
                output_dir = os.path.dirname(output_file)
                if output_dir and not os.path.exists(output_dir):
                    os.makedirs(output_dir)
                dataAnalysis_dict = {
                    "output_directory": dataAnalysis.directory,
                    "name_figures":     dataAnalysis.name_figures,
                    "colors":          dataAnalysis.color,
                    "output_table": convert_keys_to_str(dataAnalysis.OutputTable)
                }
                with open(output_file, 'w') as f:
                    json.dump(dataAnalysis_dict, f, indent=2, default=str)
                print(f"DataAnalysis saved to {output_file}")
            

            # Sort rows consistently before producing plots. The sort keys are
            # gateway, end-device count, confirmed percentage, and period.
            dataAnalysis.sort_outputTable("gw,ed,p,pe")



            #Simulator.traffic_gen.export_frames_to_csv("uplinks.csv")
            # Generate the comparison figures. These calls read the aggregated
            # DataAnalysis table and do not rerun the simulation.
            print("Simulation completed. Statistics:")
            #dataAnalysis.printReport(Scheduler1)
            #dataAnalysis.printReport(Scheduler2)
            dataAnalysis.plot_ack_percentages_by_param('gw', metric='ACK%', limit=100, label="ACK (%)")
            dataAnalysis.plot_ack_percentages_by_param('p', metric='ACK%', limit=100, label="ACK (%)")

            dataAnalysis.plot_ack_percentages_by_param('p', metric='CPSR', limit=100, label="CPSR (%)")
            dataAnalysis.plot_ack_percentages_by_param('p',"used_rx2_percentage_total",limit=100, label="Used Rx2 (%)")
            dataAnalysis.plot_ack_heatmap_by_param('p',"Energy_Consumption_average_ed",1,True)#this includes the scheduling
            dataAnalysis.plot_ack_percentages_by_param('p', metric="Energy_Consumption_average_ed", limit=5.5, label="Battery Duration (years)",scale=1.0,lm_inf=2.5)
            dataAnalysis.plot_ack_percentages_by_param('p', metric="Jains_index", limit=1.0, label="Jain's Index",scale=1.0)
            dataAnalysis.plot_duty_cycle_consumption("Duty Cycle Consumption","gw",'DC' )
            dataAnalysis.plot_ack_heatmap_by_param('p',"CPSR")#this includes the scheduling
            dataAnalysis.plot_ack_heatmap_by_param('p',"ACK%")#this includes the scheduling

            #dataAnalysis.plot_ack_heatmap_by_param('p',"downlinkReceivedByED")#this includes the scheduling
            
            #dataAnalysis.plot_ack_heatmap_by_param('p')#this includes the scheduling
            dataAnalysis.plot_ack_percentages_by_param('p',"duty_cycle_Rx1_left")
            dataAnalysis.plot_ack_percentages_by_param('p',"duty_cycle_Rx2_left")
            #dataAnalysis.plot_ack_percentages_by_sf()
            dataAnalysis.plot_ack_percentages_by_param('p',"Loss_half_duplex%", limit=30, label="Loss Half Duplex (%)")
            dataAnalysis.plot_ack_percentages_by_sf('DL_PDR_sf')
            #dataAnalysis.plot_ack_percentages_by_sf('DL_PDR_total_sf')
            #dataAnalysis.plot_ack_percentages_by_sf('SF_COUNT_sf',50)
            dataAnalysis.plot_ack_percentages_by_sf('USE_Rx1_sf')
            dataAnalysis.plot_ack_percentages_by_sf('USE_Rx2_sf')
            #dataAnalysis.plot_ack_percentages_by_param('p',"downlinkReceivedByED")
            #dataAnalysis.plot_ack_heatmap_by_param('p',"used_rx1_percentage_total")
            #dataAnalysis.plot_ack_heatmap_by_param('p',"used_rx2_percentage_total")
            #plt.show()

# Convert tuple keys to strings for JSON serialization
def convert_keys_to_str(d):
    """Recursively convert dictionary keys to strings"""
    if isinstance(d, dict):
        return {str(k): convert_keys_to_str(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [convert_keys_to_str(item) for item in d]
    return d

def try_parse_tuple_key(k):
    """Try to parse a string key back to a tuple of ints, e.g. '(100, 1, 50, 360)' -> (100, 1, 50, 360)"""
    stripped = k.strip()
    if stripped.startswith('(') and stripped.endswith(')'):
        try:
            return tuple(int(x.strip()) for x in stripped[1:-1].split(','))
        except ValueError:
            pass
    return k

def convert_keys_from_str(d, depth=0):
    """Recursively restore tuple keys at depth 1 (param level) of OutputTable"""
    if isinstance(d, dict):
        return {(try_parse_tuple_key(k) if depth == 1 else k): convert_keys_from_str(v, depth + 1) for k, v in d.items()}
    elif isinstance(d, list):
        return [convert_keys_from_str(item, depth) for item in d]
    return d
if __name__ == "__main__":
    main()