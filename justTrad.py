from NetworkServer import NetworkServer
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
from OptimalSchedulling import OptimalSchedulling
import os
import glob
import re
import matplotlib.pyplot as plt
FULLDUPLEX = False
MODEL = "okumura"  # Change to "log" for log-distance path loss model
DUTY_CYCLE = "blocked"  # Change to "blocked" for blocked duty cycle approach
OUTPUT_IMAGES = "output_images/Final_Plots"  # Directory to save output images
EXTRA = "trad_comp"  # Extra identifier for output files
CONSIDER_OPTIMAL = True  # Whether to compute and include optimal scheduling results
IMPORT_DATAANLAYSIS = True  # Whether to import existing DataAnalysis JSON instead of re-running simulations
#teste Processing file: 10REPETITION_HEURISTIC_SCORE_TEST_TTS_stats_period_360_gateway_2_seed_180000_percentage_50_log_N_ED_100_log_uplinks.csv
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
    uplinks_dir = "UplinksLogs"  # Directory containing the uplink CSV files
    #uplinks_dir = "TESTING_FRAME_COUNTERE_OKURA"
    #uplinks_dir = "10_REPETITION_HEURISTIC_SCORE"
    #uplinks_dir ="10_RUNS_NORMAL_LORAWAN_FOR_GLOBECOM_COMPARISON_FIXED_VERSION"
    uplinks_files = glob.glob(os.path.join(uplinks_dir, "*_uplinks.csv"))
    colors_TTS_CUS_OP = ['orange','seagreen','salmon']
    
    # Initialize classes
    dataAnalysis = DataAnalysis()
# Scheduler names configuration
    SCHEDULER_NAMES = {
        "scheduler_1": "WSBS",  # Replace with desired scheduler name
        "scheduler_2": "SHBS",  # Replace with desired scheduler name
        "scheduler_3": "IABS",  # Replace with desired scheduler name
        "scheduler_4": "DCBS",  # Replace with desired scheduler name
        "scheduler_5": "TTS",  # Replace with desired scheduler name
        "scheduler_6": "SFTS",  # Replace with desired scheduler name
        "scheduler_7": "Optimal"  # Replace with desired scheduler name
    }
    resources = {
            'Rx1_duty_cycle': 1,  # Example duty cycle for Rx1
            'Rx2_duty_cycle': 10   # Example duty cycle for Rx2v
        }
    for file in uplinks_files:
        for duty_cycle_management in ["blocked"]:
            param= extract_parameters(file)

            print(f"Computing Traditional Processing file: {file}")
            schedul_name = SCHEDULER_NAMES["scheduler_5"]

            scheduler = SchedulerTraditional("TRADITIONAL", resources, duty_cycle_management)
            # Create a new instance of SimulatorCore with the scheduler
            Simulator = SimulatorCore(file,scheduler,"dump/INFO_"+schedul_name+str(param),False, FULLDUPLEX,MODEL)

            # Register end devices and gateways
            Simulator.register_end_device_gateway()

            # Simulate the network

            Simulator.simulate()

            dataAnalysis.add_data_outputTable(schedul_name, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[0])


            scheduler = TraditionalThreshold("TRADITIONAL", resources, 9, duty_cycle_management)
            Simulator = SimulatorCore(file, scheduler,"dump/INFO_"+schedul_name+str(param),False, FULLDUPLEX,MODEL)
            # Register end devices and gateways
            Simulator.register_end_device_gateway()
            # Simulate the network
            Simulator.simulate()
            dataAnalysis.add_data_outputTable(schedul_name, param, Simulator.logger.compute_statistics(),colors_TTS_CUS_OP[1])

        """         
        param= extract_parameters(file)
        schedul_name = "Threshold"

        scheduler = TraditionalThreshold("TRADITIONAL", resources, 9, "blocked")
        Simulator = SimulatorCore(file, scheduler,"dump/INFO_"+schedul_name+str(param))

        # Register end devices and gateways
        Simulator.register_end_device_gateway()

        # Simulate the network

        Simulator.simulate()
        dataAnalysis.add_data_outputTable(schedul_name, param, Simulator.logger.compute_statistics())
        """


        """        
        print(f"Computing Traditional Processing file: {file}")
        schedul_name = "TRAD-Budget"
        scheduler = SchedulerTraditional("TRADITIONAL", resources,"budget")
        # Create a new instance of SimulatorCore with the scheduler
        Simulator = SimulatorCore(file,scheduler,"dump/INFO_"+schedul_name+str(param))

        # Register end devices and gateways
        Simulator.register_end_device_gateway()

        # Simulate the network
        param= extract_parameters(file)

        Simulator.simulate()

        dataAnalysis.add_data_outputTable(schedul_name, param, Simulator.logger.compute_statistics()) """
    


    # opT_1 = OptimalSchedulling(uplinks_dir)
    # # #opT_2 = OptimalSchedulling(uplinks_dir,"BUDGET")

    # # #ALL_results_2,dc_results_2,stats_2 = opT_2.run()
    # ALL_results,dc_results_1,stats_1 = opT_1.run()
    # for key in ALL_results:
    #     dataAnalysis.add_data_outputTable("Optimal_Blocked", key, stats_1[key], colors_TTS_CUS_OP[2])

    #for key in ALL_results_2:
        #dataAnalysis.add_data_outputTable("Optimal_Budget", key, stats_2[key])
    



    dataAnalysis.sort_outputTable("gw,ed,p,pe")



    #Simulator.traffic_gen.export_frames_to_csv("uplinks.csv")
    # Print the statistics
    print("Simulation completed. Statistics:")
    #dataAnalysis.printReport(Scheduler1)
    #dataAnalysis.printReport(Scheduler2)
    dataAnalysis.plot_ack_percentages_by_param(split_param='gw', metric='ACK%')
    dataAnalysis.plot_ack_heatmap_by_param('p')
    dataAnalysis.plot_ack_heatmap_by_param('p',"CPSR")

    dataAnalysis.plot_ack_heatmap_by_param_separated('p')
    dataAnalysis.plot_duty_cycle_consumption()
    #dataAnalysis.plot_ack_percentages_by_param('p',"duty_cycle_Rx1_left")
    #dataAnalysis.plot_ack_percentages_by_param('p',"duty_cycle_Rx2_left")
    #dataAnalysis.plot_ack_percentages_by_sf()
    #dataAnalysis.plot_ack_percentages_by_param('p',"Loss_half_duplex%")
    #dataAnalysis.plot_ack_percentages_by_sf('DL_PDR_sf')
    #dataAnalysis.plot_ack_percentages_by_sf('DL_PDR_total_sf')
    #dataAnalysis.plot_ack_percentages_by_sf('SF_COUNT_sf',50)
    dataAnalysis.plot_ack_percentages_by_sf('USE_Rx1_sf')
    dataAnalysis.plot_ack_percentages_by_sf('USE_Rx2_sf')
    #dataAnalysis.plot_ack_percentages_by_param('p',"downlinkReceivedByED")

    plt.show()


if __name__ == "__main__":
    main()