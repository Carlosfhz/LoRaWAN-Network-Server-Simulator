from NetworkServer import NetworkServer
from OptimalSchedulling import OptimalSchedulling
from SchedulerBudgetGreedyEntropy_RSSI import SchedulerBudgetGreedyEntropy_RSSI
from SchedulerBudgetGreedy_RSSI import SchedulerBudgetGreedy_RSSI
from SchedulerBudgetGreedyEntropy_RSSI_v2 import SchedulerBudgetGreedyEntropy_RSSI_v2
import TraditionalThreshold_ALLGW
from TrafficGeneration import TrafficGeneration
from SimulatorCore import SimulatorCore
from DataAnalysis import DataAnalysis
from SchedulerTraditional import SchedulerTraditional
from SchedulerContextualAB import SchedulerContextualAB
from SchedulerEpsilonGreedy import SchedulerEpsilonGreedy
from ScheduleThompsonSampling import ScheduleThompsonSampling
from SchedulerUCB import SchedulerUCB
from ScheduleQtables import ScheduleQtables
from ExperimentalScheduler import ExperimentalScheduler
from TraditionalThreshold import TraditionalThreshold
from SchedulerWeighted import SchedulerWeighted
from SchedulerContextualAB_BASIC import SchedulerContextualAB_BASIC
from SchedulerNeuralUCB import SchedulerNeuralUCB
from SchedulerEXP3 import SchedulerEXP3
from TraditionalThreshold_ALLGW import TraditionalThreshold_ALLGW
from TraditionalDownlinkScheduling_ALLGW import TraditionalDownlinkScheduling_ALLGW
from SchedulerContextualAB_Stochastic import SchedulerContextualAB_Stochastic
from MIX_MAB import MIX_MAB
from KnwonReward import KnwonReward
from SchedulerUCBStochasticReward import SchedulerUCBStochasticReward
from SchedulerBudgetGreedy import SchedulerBudgetGreedy
from SchedulerContextualAB_Stochastic_Hybrid import SchedulerContextualAB_Stochastic_Hybrid
from SchedulerContextualAB_TS import SchedulerContextualAB_new_reward
from SchedulerBudgetGreedyEntropy import SchedulerBudgetGreedyEntropy
from SchedulerContextualAB_simple import SchedulerContextualAB_simple
import matplotlib.pyplot as plt
import os
import glob
import re
import json
import time
MODEL = "okumura"  # Change to "log" for log-distance path loss model
DUTY_CYCLE = "blocked"  # Change to "blocked" for blocked duty cycle approach
OUTPUT_IMAGES = "output_images"  # Directory to save output images
EXTRA = "weighted_score"  # Extra identifier for output files
def extract_parameters(filename):
    # Extract parameters from filename using regex
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
    # Define the CSV file name
    #csv_file_name = "test_example.csv"
    #csv_file_name = "UplinksLogs/TESTING_TTS_NORMAL_RECREATION_CONSECUTIVE_TTS_stats_period_360_gateway_1_seed_250_percentage_50_log_N_ED_400_log_uplinks.csv"  # Example CSV file name, replace with your actual file
    #uplinks_dir = "UplinksLogsREDUCED"
    #uplinks_dir = "Multi_gateway_study"
    #uplinks_dir = "Uplinks_long/50"
    #uplinks_dir = "UplinkLogs_1gw"
    #uplinks_dir = "UplinksLogs"  # Directory containing the uplink CSV files
    #uplinks_dir = "10_REPETITION_HEURISTIC_SCORE"
    uplinks_dir = "10_REPETITIONS_OKUMARA_RANDOM_FULL"
    #uplinks_dir = "10_REPETITION_HEURISTIC_SCORE_SHORT"
    #uplinks_dir ="10_RUNS_NORMAL_LORAWAN_FOR_GLOBECOM_COMPARISO
    # N_FIXED_VERSION"
    #uplinks_dir = "TESTING_MULTI_GATEWAY_SIM_TIME_3HOURS"
    #uplinks_dir = "testing_multi_gateway_sim_time_8_hours"
    #uplinks_dir = "Limited_A_lot"

    results_file = f"RESULTS_OPTIMAL_{uplinks_dir}_{DUTY_CYCLE}.json"
    uplinks_files = glob.glob(os.path.join(uplinks_dir, "*_uplinks.csv"))
    # Initialize classes
    dataAnalysis = DataAnalysis(OUTPUT_IMAGES,uplinks_dir+f"_{DUTY_CYCLE}_{EXTRA}")  # Directory to save output images and name prefix
    #dataAnalysis_b = DataAnalysis()
    Scheduler0 = "UCB_new"
    Scheduler3 = "Threshold"
    Scheduler33 = "Threshold all GW"
    Scheduler44 = "Traditional all GW"
    Scheduler4 = "Traditional"
    Scheduler2  = "EXP3"
    Scheduler1 = "MIX_MAB"
    Scheduler5 = "ContextualAB_1_0"
    Scheduler55 = "ContextualAB_1_5"
    Scheduler555 = "ContextualAB_0_5"
    Scheduler5_1 = "ContextualAB_Hybrid"
    scheduler_6 = "Qtables"
    colors_TTS_CUS_OP = ['orange','seagreen','salmon','magenta']

    Scheduler6 = "KnownReward"
    resources = {
            'Rx1_duty_cycle': 1,  # Example duty cycle for Rx1
            'Rx2_duty_cycle': 10   # Example duty cycle for Rx2v
        }
    Counter = 0
    for file in uplinks_files:
        param= extract_parameters(file)  
        # print(f"Computing Contextual AB Stochastic file: {file}")
        # scheduler = ScheduleQtables("ARMED", resources, "blocked")
        # Simulator = SimulatorCore(file, scheduler,"dump/INFO_"+scheduler_6+str(param))   
        # Simulator.register_end_device_gateway()
        # Simulator.simulate()        
        # dataAnalysis.add_data_outputTable(scheduler_6, param, Simulator.logger.compute_statistics())
        """ 
        print(f"Computing Budget Greedy scheduler file: {file}")
        SchedulerBudget = "WeightedGreedy"
        scheduler = SchedulerBudgetGreedy_RSSI("ARMED", resources, "blocked", False)
        Simulator = SimulatorCore(file, scheduler, "dump/INFO_"+SchedulerBudget+str(param),False,False,MODEL)
        Simulator.register_end_device_gateway()
        Simulator.simulate()
        dataAnalysis.add_data_outputTable(SchedulerBudget, param, Simulator.logger.compute_statistics())
        """

        print(f"Computing Budget Greedy Entropy scheduler file: {file}")
        SchedulerBudgetEntropy = "WSS"

        # if SchedulerBudgetEntropy in dataAnalysis.OutputTable and param in dataAnalysis.OutputTable[SchedulerBudgetEntropy]:
        #     if len(dataAnalysis.OutputTable[SchedulerBudgetEntropy][param])> 3:
        #         print(f"Skipping {file} for {SchedulerBudgetEntropy} as it has already been processed.")
        #         continue

        scheduler = SchedulerBudgetGreedyEntropy_RSSI_v2("ARMED", resources, DUTY_CYCLE, False)
        Simulator = SimulatorCore(file, scheduler, "dump/INFO_"+SchedulerBudgetEntropy+str(param),False,False,MODEL)
        Simulator.register_end_device_gateway()
        Simulator.simulate()
        dataAnalysis.add_data_outputTable(SchedulerBudgetEntropy, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[3])

        SchedulerBudgetEntropy = "WSS_2_5"

        # if SchedulerBudgetEntropy in dataAnalysis.OutputTable and param in dataAnalysis.OutputTable[SchedulerBudgetEntropy]:
        #     if len(dataAnalysis.OutputTable[SchedulerBudgetEntropy][param])> 3:
        #         print(f"Skipping {file} for {SchedulerBudgetEntropy} as it has already been processed.")
        #         continue

        scheduler = SchedulerBudgetGreedyEntropy_RSSI_v2("ARMED", resources, DUTY_CYCLE, False, SF_IMPACT= 0.0,W_RSSI = 0.33, W_SNR=0.33, W_BLOCK=0.34, W_RATE=1, W_AVAIL=1, GAMMA=0.1,THRESHOLD_BLOCKED=0.25)
        Simulator = SimulatorCore(file, scheduler, "dump/INFO_"+SchedulerBudgetEntropy+str(param),False,False,MODEL)
        Simulator.register_end_device_gateway()
        Simulator.simulate()
        dataAnalysis.add_data_outputTable(SchedulerBudgetEntropy, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[3])  
        SchedulerBudgetEntropy = "WSS_3.5"

        # if SchedulerBudgetEntropy in dataAnalysis.OutputTable and param in dataAnalysis.OutputTable[SchedulerBudgetEntropy]:
        #     if len(dataAnalysis.OutputTable[SchedulerBudgetEntropy][param])> 3:
        #         print(f"Skipping {file} for {SchedulerBudgetEntropy} as it has already been processed.")
        #         continue

        scheduler = SchedulerBudgetGreedyEntropy_RSSI_v2("ARMED", resources, DUTY_CYCLE, False, SF_IMPACT= 0.0,W_RSSI = 0.33, W_SNR=0.33, W_BLOCK=0.34, W_RATE=1, W_AVAIL=1, GAMMA=0.1,THRESHOLD_BLOCKED=0.35)
        Simulator = SimulatorCore(file, scheduler, "dump/INFO_"+SchedulerBudgetEntropy+str(param),False,False,MODEL)
        Simulator.register_end_device_gateway()
        Simulator.simulate()
        dataAnalysis.add_data_outputTable(SchedulerBudgetEntropy, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[3])  

        SchedulerBudgetEntropy = "WSS_5"

        # if SchedulerBudgetEntropy in dataAnalysis.OutputTable and param in dataAnalysis.OutputTable[SchedulerBudgetEntropy]:
        #     if len(dataAnalysis.OutputTable[SchedulerBudgetEntropy][param])> 3:
        #         print(f"Skipping {file} for {SchedulerBudgetEntropy} as it has already been processed.")
        #         continue

        scheduler = SchedulerBudgetGreedyEntropy_RSSI_v2("ARMED", resources, DUTY_CYCLE, False, SF_IMPACT= 0.0,W_RSSI = 0.33, W_SNR=0.33, W_BLOCK=0.34, W_RATE=1, W_AVAIL=1, GAMMA=0.1,THRESHOLD_BLOCKED=0.5)
        Simulator = SimulatorCore(file, scheduler, "dump/INFO_"+SchedulerBudgetEntropy+str(param),False,False,MODEL)
        Simulator.register_end_device_gateway()
        Simulator.simulate()
        dataAnalysis.add_data_outputTable(SchedulerBudgetEntropy, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[3])  



        name_scheduler = "SFTS"
        scheduler = TraditionalThreshold("TRADITIONAL", resources, 9, DUTY_CYCLE)
        Simulator = SimulatorCore(file, scheduler,"dump/INFO_"+name_scheduler+str(param),False,False,MODEL)
        # Register end devices and gateways
        Simulator.register_end_device_gateway()
        # Simulate the network
        Simulator.simulate()
        dataAnalysis.add_data_outputTable(name_scheduler, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[1])
       


        print(f"Computing Traditional Processing file: {file}")
        name_scheduler = "TTS"
        scheduler = SchedulerTraditional("TRADITIONAL", resources,DUTY_CYCLE)
        # Create a new instance of SimulatorCore with the scheduler
        Simulator = SimulatorCore(file,scheduler,"dump/INFO_"+name_scheduler+str(param),False,False,MODEL)
        # Register end devices and gateways
        Simulator.register_end_device_gateway()
        # Simulate the network
        Simulator.simulate()
        table = Simulator.logger.compute_statistics()
        dataAnalysis.add_data_outputTable(name_scheduler, param, table,colors_TTS_CUS_OP[0])

        Counter +=1
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Completed {Counter}/{len(uplinks_files)} files")








    """ 
        print(f"Computing Traditional Threshold all GW file: {file}")
        scheduler = TraditionalThreshold_ALLGW("TRADITIONAL",resources, 9,DUTY_CYCLE)
        Simulator = SimulatorCore(file,scheduler,"dump/INFO_"+Scheduler33+str(param),False,False,DUTY_CYCLE)
        Simulator.register_end_device_gateway()
        Simulator.simulate()
        dataAnalysis.add_data_outputTable(Scheduler33, param, Simulator.logger.compute_statistics())

        print(f"Computing Traditional all GW file: {file}")
        scheduler = TraditionalDownlinkScheduling_ALLGW("TRADITIONAL", resources,DUTY_CYCLE)
        Simulator = SimulatorCore(file,scheduler,"dump/INFO_"+Scheduler44+str(param),False,False,DUTY_CYCLE)
        Simulator.register_end_device_gateway()
        Simulator.simulate()
        dataAnalysis.add_data_outputTable(Scheduler44, param, Simulator.logger.compute_statistics())
    """

    
    if os.path.exists(results_file):
        print(f"Loading existing results from {results_file}")
        with open(results_file, 'r') as f:
            data = json.load(f)
            stats_1 = data.get("stats", {})
    else:
        print(f"Results file not found. Running OptimalSchedulling...")
        opT_1 = OptimalSchedulling(uplinks_dir,DUTY_CYCLE)
        ALL_results, dc_results_1, stats_1 = opT_1.run()
        
        if ALL_results and stats_1:
            stats_str_keys = convert_keys_to_str(stats_1)
            with open(results_file, 'w') as f:
                json.dump({
                    "uplinks_dir": uplinks_dir,
                    "stats": stats_str_keys
                }, f, indent=2, default=str)

    for param_key in stats_1:
        param = tuple(map(int, param_key.strip('()').split(', '))) if isinstance(param_key, str) else param_key
        for stats in stats_1[param_key]:
            dataAnalysis.add_data_outputTable("Optimal", param, stats, colors_TTS_CUS_OP[2])


    dataAnalysis.sort_outputTable("gw,ed,p,pe")

        #Simulator.traffic_gen.export_frames_to_csv("uplinks.csv")
    # Print the statisticsq
    print("Simulation completed. Statistics:")
    #dataAnalysis.printReport(Scheduler1)
    #dataAnalysis.printReport(Scheduler2)
    dataAnalysis.plot_ack_percentages_by_param(split_param='gw', metric='ACK%')
    dataAnalysis.plot_ack_percentages_by_param(split_param='p', metric='Loss_half_duplex%',limit=25, label="Half Duplex Loss (%)")
    dataAnalysis.plot_ack_percentages_by_param(split_param='p', metric='duty_cycle_Rx1_left',limit=100, label="Duty Cycle Rx1 Left (%)")
    dataAnalysis.plot_ack_percentages_by_param(split_param='p', metric='duty_cycle_Rx2_left',limit=100, label="Duty Cycle Rx2 Left (%)")

    dataAnalysis.plot_ack_heatmap_by_param('p')
    dataAnalysis.plot_ack_heatmap_by_param('p',"downlinkReceivedByED")
    dataAnalysis.plot_ack_heatmap_by_param('p',"CPSR")#this includes the scheduling
    dataAnalysis.plot_ack_percentages_by_param('p', metric='CPSR', limit=100, label="CPSR (%)")

    #dataAnalysis.plot_ack_heatmap_by_param('p',"duty_cycle_Rx1_left")
    #dataAnalysis.plot_ack_heatmap_by_param('p',"duty_cycle_Rx2_left")
    #dataAnalysis.plot_ack_heatmap_by_param('p',"Final_Reward",1)
    dataAnalysis.plot_ack_heatmap_by_param('p',"used_rx1_percentage_total")
    dataAnalysis.plot_ack_heatmap_by_param('p',"used_rx2_percentage_total")

    #dataAnalysis.plot_ack_percentages_by_sf()
    dataAnalysis.plot_ack_percentages_by_sf('USE_Rx2_sf',100, "Rx2 by SF","Rx2%")
    dataAnalysis.plot_ack_percentages_by_sf('USE_Rx1_sf',100, "Rx1 by SF","Rx1%")


    plt.show()
# Convert tuple keys to strings for JSON serialization
def convert_keys_to_str(d):
    """Recursively convert dictionary keys to strings"""
    if isinstance(d, dict):
        return {str(k): convert_keys_to_str(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [convert_keys_to_str(item) for item in d]
    return d

if __name__ == "__main__":
    main()