import os
import pandas as pd
import pulp 
import math
import time
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
WITH_COUNTER = True

class OptimalSchedulling():
    def __init__(self, directory, mode = 'BLOCKED'):
        self.directory = directory
        self.toa_cache = {}  # Cache for TimeOnAir calculations
        self.payload_size = 12  # Assuming a fixed payload size for calculations
        self.Rx1_budget = 36
        self.mode = mode
        self.Rx2_budget = 360
        self.SF_ed = {}


    
    def _extract_table_with_headers(self,file_path, headers):
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
    def run(self):
        ALL_results = {}
        dc_results = {}
        stats = {}
        for file in os.listdir(self.directory):
            if not file.endswith('_uplinks.csv'):
                continue
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}] - Processing file: {file}")
            # Extract values from filename
            parts = file.replace('.csv', '').split('_')
            num_gateways = int(parts[parts.index('gateway') + 1])
            seed = int(parts[parts.index('seed') + 1])
            percentage_confirm = int(parts[parts.index('percentage') + 1])
            num_end_devices = int(parts[parts.index('ED') + 1])
            period = int(parts[parts.index('period') + 1])
            

            # Look for the table with the required headers
            target_headers = ['senderId', 'receiverID', 'sendTime', 'receivedTime', 'SF', 'SNR', 'Ftype', 'Freq', 'received', 'code','']
            target_headers_with_counter = ['senderId', 'receiverID', ' sendTime', ' receivedTime', 'SF', 'SNR','RSSI', 'Ftype', ' Freq', 'n_frame', 'received', 'code','']
            numeric_columns = ['sendTime', 'receivedTime', 'SF', 'SNR', 'Freq', 'received', 'code']
            sendTime_code = 'sendTime'
            receivedTime_code = 'receivedTime'
            if WITH_COUNTER:
                target_headers = target_headers_with_counter
                numeric_columns = [' sendTime', ' receivedTime', 'SF', 'SNR', 'RSSI', ' Freq', 'n_frame', 'received', 'code']
                sendTime_code = ' sendTime'
                receivedTime_code = ' receivedTime'
                
            df = self._extract_table_with_headers(os.path.join(self.directory, file), target_headers)
            # Convert numeric columns to float

            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            df_sorted = df.sort_values(by=sendTime_code)
            # Extract the first sendTime value
            first_send_time = df_sorted[sendTime_code].iloc[0]
            # Shift all sendTime values so the first one becomes 0
            df_sorted[sendTime_code] = (df_sorted[sendTime_code] - first_send_time) / 1e9
            df_sorted[receivedTime_code] = (df_sorted[receivedTime_code] - first_send_time) / 1e9
            Uc_n, ed_sf = self._get_uplinks(df_sorted, sendTime_code, receivedTime_code)

            self.SF_ed[(num_end_devices,num_gateways,percentage_confirm,period)] = ed_sf
            #print(Uc_n)
            #print(df_sorted)
                    # Use faster solver settings
   
            result,result_per_arrival = self.LIP_problem(Uc_n, ed_sf)
            if (num_end_devices,num_gateways,percentage_confirm,period) not in ALL_results:
                ALL_results[(num_end_devices,num_gateways,percentage_confirm,period)] = []
                dc_results[(num_end_devices,num_gateways,percentage_confirm,period)] = []
                stats[(num_end_devices,num_gateways,percentage_confirm,period)] = []
            ALL_results[(num_end_devices,num_gateways,percentage_confirm,period)].append(result_per_arrival)
            duty_cycle_consumption = self.compute_duty_cycle_consumption(ALL_results)
            dc_results[(num_end_devices,num_gateways,percentage_confirm,period)].append(duty_cycle_consumption)
            stats[(num_end_devices,num_gateways,percentage_confirm,period)].append(self.compute_statistics(result,duty_cycle_consumption))


        return ALL_results,dc_results,stats



    def _get_uplinks(self, df, sendTime_code='sendTime', receivedTime_code='receivedTime'):
        """Extract uplink information from DataFrame"""
        ul = df[df['Ftype'].astype(int) == 4].copy()
        Uc_n = {}
        ed_sf = {}
        for row in ul[['senderId', 'receiverID', sendTime_code, receivedTime_code, 'SF']].itertuples(index=False):
            ed_id = int(row[0])
            gw_id = int(row[1])
            send_time = float(row[2])
            receive_time = float(row[3])
            sf = int(row[4])
            ed_sf[ed_id] = sf
            if ed_id not in Uc_n:
                Uc_n[ed_id] = {}
            if send_time not in Uc_n[ed_id]:
                Uc_n[ed_id][send_time] = []
            Uc_n[ed_id][send_time].append((gw_id, (send_time, receive_time)))
        return Uc_n, ed_sf
    def LIP_problem(self,Uc_n, ed_sf):
        """
        Linear Integer Programming problem for downlink scheduling optimization
        """
        alphas = [1, 1, 1, 1, 1, 1]
        
        
        
        # Create optimization problem and variables
        m = pulp.LpProblem("DownlinkScheduling", pulp.LpMaximize)
        y1 = {}
        y2 = {}
        y_coll = {}
        objective_terms = []
        alpha = 10e-5
        Gr = []
        for n in Uc_n:
            for j, send_time in enumerate(Uc_n[n]):
                tnj_g_list = Uc_n[n][send_time]
                y_coll_n_j = pulp.LpVariable(f"ycoll_{n}_{j}", cat='Binary')
                y_coll[(n,j)] = y_coll_n_j
                for (g, (s_t, e_t)) in tnj_g_list:
                    if g not in Gr:
                        Gr.append(g)         
                    y1_g_n_j = pulp.LpVariable(f"y1_{g}_{n}_{j}", cat='Binary')
                    y2_g_n_j = pulp.LpVariable(f"y2_{g}_{n}_{j}", cat='Binary')
                    y1[(g,n,j)] = y1_g_n_j
                    y2[(g,n,j)] = y2_g_n_j
                    objective_terms.append(((1+alpha) * (y1_g_n_j) + y2_g_n_j))
                    
        Y_b = {"y1": y1, "y2": y2, "y_coll": y_coll}            
        m += pulp.lpSum(objective_terms)
        
        # Single combined pass: compute overlaps, duty-cycle pairs, and rx budget terms
        _t0 = time.perf_counter()
        (overlap_rx1_any, overlap_rx2_any, overlap_ul_with_dl,
         dc_rx1_pairs, dc_rx2_pairs,
         rx1_terms_gw, rx2_terms_gw) = self._compute_all(Uc_n, ed_sf, Y_b, Gr)
        print(f"[LIP] _compute_all:       {time.perf_counter() - _t0:.3f}s")

        # Add all constraints
        _t0 = time.perf_counter()
        self._add_constraints(m, Y_b, y_coll, Uc_n, Gr, ed_sf,
                            overlap_rx1_any, overlap_rx2_any,
                            overlap_ul_with_dl,
                            dc_rx1_pairs, dc_rx2_pairs,
                            rx1_terms_gw, rx2_terms_gw)
        print(f"[LIP] _add_constraints:   {time.perf_counter() - _t0:.3f}s")
        
        # Solve and extract results
        # Save model to text file before solving
        _t0 = time.perf_counter()
        #m.writeLP("model_n.lp")
        print(f"[LIP] writeLP:            {time.perf_counter() - _t0:.3f}s")

        solver = pulp.HiGHS_CMD(
            path="/opt/homebrew/bin/highs",
            msg=1,
            gapRel=0.01,
            threads=4,
        )
        print("[LIP] solver: HiGHS", flush=True)

        _t0 = time.perf_counter()
        print("[LIP] solve started", flush=True)
        solve_status = m.solve(solver)
        print(f"[LIP] solve finished:     {time.perf_counter() - _t0:.3f}s", flush=True)
        print(f"[LIP] status:             {pulp.LpStatus[solve_status]}", flush=True)
        
        """        
        # Print the results of y1 and y2 variables
        for (g, n, j), var in y1.items():
            value = pulp.value(var)
            if value and value > 0.5:
                print(f"  y1[g={g}, n={n}, j={j}] = {value}")


        for (g, n, j), var in y2.items():
            value = pulp.value(var)
            if value and value > 0.5:
                print(f"  y2[g={g}, n={n}, j={j}] = {value}")

        
        for (n, j), var in y_coll.items():
            value = pulp.value(var)
            if value and value > 0.5:
                print(f"  y_coll[n={n}, j={j}] = {value}")"""

        return self._extract_results(y1, y2,y_coll, Uc_n,ed_sf)
    
    def _compute_all(self, Uc_n, ed_sf, Y_b, Gr):
        """Single combined pass: compute overlaps, duty-cycle pairs, and budget terms."""
        G = list(set(Gr))
        overlap_rx1_any    = {k: [] for k in Y_b["y1"]}
        overlap_rx2_any    = {k: [] for k in Y_b["y1"]}
        overlap_ul_with_dl = {k: [] for k in Y_b["y1"]}
        dc_rx1_pairs = {g: [] for g in G}
        dc_rx2_pairs = {g: [] for g in G}
        rx1_terms_gw = {}
        rx2_terms_gw = {}

        # Build flat list once: (n, j, g, s_t, e_t, sf, toa_rx1_ms, toa_rx2_ms,
        #                         rx1_start, rx1_end, rx2_start, rx2_end)
        flat = []
        for n in Uc_n:
            sf_n = ed_sf[n]
            toa_rx1_ms = self.get_cached_toa(self.payload_size, sf_n)
            toa_rx2_ms = self.get_cached_toa(self.payload_size, 12)
            for j, send_time in enumerate(Uc_n[n]):
                for g, (s_t, e_t) in Uc_n[n][send_time]:
                    rx1_start = e_t + 1
                    rx1_end   = e_t + 1 + toa_rx1_ms / 1000
                    rx2_start = e_t + 2
                    rx2_end   = e_t + 2 + toa_rx2_ms / 1000
                    flat.append((n, j, g, s_t, e_t, sf_n,
                                 toa_rx1_ms, toa_rx2_ms,
                                 rx1_start, rx1_end, rx2_start, rx2_end))
                    # Budget terms (linear pass)
                    hour = int(e_t // 3600)
                    key = (g, hour)
                    if key not in rx1_terms_gw:
                        rx1_terms_gw[key] = []
                        rx2_terms_gw[key] = []
                    rx1_terms_gw[key].append(Y_b["y1"][(g, n, j)] * toa_rx1_ms)
                    rx2_terms_gw[key].append(Y_b["y2"][(g, n, j)] * toa_rx2_ms)

        # Single O(N²) double loop for all pair-based checks
        for i, (n, j, g, s_t, e_t, sf_n,
                toa_rx1_ms, toa_rx2_ms,
                rx1_start, rx1_end, rx2_start, rx2_end) in enumerate(flat):
            for (n_p, j_p, g_p, s_t_p, e_t_p, sf_np,
                 toa_rx1_ms_p, toa_rx2_ms_p,
                 rx1_start_p, rx1_end_p, rx2_start_p, rx2_end_p) in flat:

                if (n, j) == (n_p, j_p) or g != g_p:
                    continue

                # ---- UL-DL half-duplex overlaps ----
                if rx1_start_p <= e_t <= rx1_end_p:
                    overlap_ul_with_dl[(g, n, j)].append(Y_b["y1"][(g_p, n_p, j_p)])
                if rx2_start_p <= e_t <= rx2_end_p:
                    overlap_ul_with_dl[(g, n, j)].append(Y_b["y2"][(g_p, n_p, j_p)])

                # ---- DL-DL overlaps ----
                if rx1_start_p < rx1_end < rx1_end_p:
                    overlap_rx1_any[(g, n, j)].append(Y_b["y1"][(g_p, n_p, j_p)])
                if rx2_start_p < rx1_end < rx2_end_p:
                    overlap_rx1_any[(g, n, j)].append(Y_b["y2"][(g_p, n_p, j_p)])
                if rx1_start_p < rx2_end < rx1_end_p:
                    overlap_rx2_any[(g, n, j)].append(Y_b["y1"][(g_p, n_p, j_p)])
                if rx2_start_p < rx2_end < rx2_end_p:
                    overlap_rx2_any[(g, n, j)].append(Y_b["y2"][(g_p, n_p, j_p)])

                # ---- Duty-cycle pairs (only consider n != n_p already guaranteed above) ----
                if n_p != n:
                    if s_t < s_t_p < s_t + 100 * toa_rx1_ms / 1000:
                        dc_rx1_pairs[g].append((Y_b["y1"][(g, n, j)], Y_b["y1"][(g_p, n_p, j_p)]))
                    if s_t < s_t_p < s_t + 10 * toa_rx2_ms / 1000:
                        dc_rx2_pairs[g].append((Y_b["y2"][(g, n, j)], Y_b["y2"][(g_p, n_p, j_p)]))

        return (overlap_rx1_any, overlap_rx2_any, overlap_ul_with_dl,
                dc_rx1_pairs, dc_rx2_pairs, rx1_terms_gw, rx2_terms_gw)




    def _add_constraints(self, m, Y_b, y_coll, Uc_n, Gr, ed_sf, 
                        overlap_rx1_any, overlap_rx2_any, overlap_ul_with_dl,
                        dc_rx1_pairs, dc_rx2_pairs,
                        rx1_terms_gw, rx2_terms_gw):
        """Add all constraints to the optimization model"""
        
        # Half-duplex constraints
        for (g,n,j), overlaps in overlap_ul_with_dl.items():
            half_duplex = overlaps
            Gr_n_j_len = len(Uc_n[n][list(Uc_n[n].keys())[j]])
            if half_duplex:
                # Half-duplex constraint: if there are overlapping transmissions, mark as collision
                # This ensures that overlapping uplink and downlink transmissions result in a collision
                # Half-duplex constraint: if there are overlapping transmissions, mark as collision
                # This ensures that overlapping uplink and downlink transmissions result in a collision
                m +=pulp.lpSum(half_duplex) - Gr_n_j_len + 1 <= Y_b["y_coll"][(n,j)],f"HalfDuplex_collision_n{n}_j{j}_g{g}"
        
        # Duty-cycle constraints
        constrint_n = 0


        if self.mode == 'blocked':
            for g, pairs in dc_rx1_pairs.items():
                for y_1_a, y_1_b in pairs:
                    
                    m += y_1_a + y_1_b <= 1, f"DutyCycle_RX1_Constraint_g{g,constrint_n}"
                    constrint_n+=1
            constrint_n = 0
            for g, pairs in dc_rx2_pairs.items():
                for y_2_a, y_2_b in pairs:
                    m += y_2_a + y_2_b <= 1, f"DutyCycle_RX2_Constraint_g{g,constrint_n}"
                    constrint_n+=1


        elif self.mode == 'mixed':
            for g, pairs in dc_rx1_pairs.items():
                for y_1_a, y_1_b in pairs:
                    
                    m += y_1_a + y_1_b <= 1, f"DutyCycle_RX1_Constraint_g{g,constrint_n}"
                    constrint_n+=1
            constrint_n = 0
            for g in Gr:
                for hour in range(24):  # Assuming 24 hours in a day
                    if (g, hour) in rx2_terms_gw:
                        # Debug: Print constraint details before adding
                        #print(f"Adding RX2 constraint for gateway {g}, hour {hour}: {len(rx2_terms_gw[(g, hour)])} terms")
                        # Proper duty cycle limit: 10% of 1 hour = 360,000 ms
                        constraint_rx2 = pulp.lpSum(rx2_terms_gw[(g, hour)]) <= 360000  # milliseconds
                        m.addConstraint(constraint_rx2, name=f"Rx2_Budget_Constraint_g{g}_hour{hour}_n{constrint_n}")
                    constrint_n += 1
        
        elif self.mode == 'budget':


            for (g,hour) in rx1_terms_gw:
                    #print(f"Adding RX1 constraint for gateway {g}, hour {hour}: {len(rx1_terms_gw[(g, hour)])} terms")
                    if (g, hour) in rx1_terms_gw:
                        # Debug: Print constraint details before adding
                        #print(f"Adding RX1 constraint for gateway {g}, hour {hour}: {len(rx1_terms_gw[(g, hour)])} terms")
                        # Proper duty cycle limit: 1% of 1 hour = 36,000 ms
                        m += pulp.lpSum(rx1_terms_gw[(g, hour)]) <= 36000  # milliseconds
                        #m.addConstraint(constraint_rx1, name=f"Rx1_Budget_Constraint_g{g}_hour{hour}_n{constrint_n}")
                    #m.addConstraint(constraint_rx1, name=f"Rx1_Budget_Constraint_g{g}_n{constrint_n}")
                    #constrint_n += 1
                    
                    if (g, hour) in rx2_terms_gw:
                        # Debug: Print constraint details before adding
                        #print(f"Adding RX2 constraint for gateway {g}, hour {hour}: {len(rx2_terms_gw[(g, hour)])} terms")
                        # Proper duty cycle limit: 10% of 1 hour = 360,000 ms
                        m += pulp.lpSum(rx2_terms_gw[(g, hour)]) <= 360000  # milliseconds
                        #m.addConstraint(constraint_rx2, name=f"Rx2_Budget_Constraint_g{g}_hour{hour}_n{constrint_n}")
                    #constrint_n += 1
        else:
            raise ValueError(f"Unknown mode: {self.mode}")


        
        # Overlap constraints
        for n in Uc_n:
            for j, send_time in enumerate(Uc_n[n]):
                Y1_Y2_g = []
                for g, (s_t, e_t) in Uc_n[n][send_time]:
                    # Rx1 and Rx2 overlap constraints
                    y1_g_n_j_overlaps = overlap_rx1_any[(g,n,j)]
                    y2_g_n_j_overlaps = overlap_rx2_any[(g,n,j)]

                    # Mutual exclusion and 
                    if y1_g_n_j_overlaps:
                        m += Y_b["y1"][(g,n,j)] + pulp.lpSum(y1_g_n_j_overlaps) <= 1, f"Rx1 Overlap Constraint{n}_j{j}_g{g}"
                    if y2_g_n_j_overlaps:   
                        m += Y_b["y2"][(g,n,j)] + pulp.lpSum(y2_g_n_j_overlaps) <= 1, f"Rx2 Overlap Constraint{n}_j{j}_g{g}"

                    
                    Y1_Y2_g .append(Y_b["y1"][(g,n,j)])
                    Y1_Y2_g .append(Y_b["y2"][(g,n,j)])
                    m += Y_b["y1"][(g,n,j)] + Y_b["y2"][(g,n,j)] <= 1,f"Rx1 or Rx2 Constraint{n}_j{j}_g{g}"


            

            
                m +=pulp.lpSum(Y1_Y2_g) <= 1 - Y_b["y_coll"][(n,j)], f"ACK Only if Received (ED:{n}_j:{j}_g:{g}): "
        
    def plot_scheduling_results(self, all_results, title="Packet Scheduling Timeline"):
                """
                Plot scheduling results over time for all scenarios
                
                Args:
                    all_results: Dictionary with scenario parameters as keys and list of repetition results as values
                             Structure: {(num_gateways, percentage_confirm, num_end_devices): [(result_summary, results_per_arrival), ...]}
                    title: Plot title
                """

                
                send_times = []
                rx1_scheduled = []
                rx2_scheduled = []
                scenario_labels = []
                
                # Define colors for different scenarios
                colors = list(mcolors.TABLEAU_COLORS.keys())
                
                # Extract data for plotting from all scenarios
                scenario_idx = 0
                for scenario_params, repetition_results in all_results.items():
                    # Take only the first repetition (index 0)
                    if repetition_results:
                        results_per_arrival = repetition_results[0]
                        scenario_label = f"GW:{scenario_params[0]}, Conf:{scenario_params[1]}%, ED:{scenario_params[2]}"
                        
                        # Extract data for this scenario
                        for send_time in sorted(results_per_arrival.keys()):
                            for (g, n), [rx1, rx2] in results_per_arrival[send_time].items():
                                send_times.append(send_time)
                                rx1_scheduled.append(1 if rx1 else 0)
                                rx2_scheduled.append(2 if rx2 else 0)  # Use 2 to distinguish from RX1
                                scenario_labels.append(scenario_idx)
                        scenario_idx += 1
                
                # Create subplots for each scenario
                unique_scenarios = len(all_results)
                fig, axes = plt.subplots(unique_scenarios, 1, figsize=(15, 4 * unique_scenarios))
                if unique_scenarios == 1:
                    axes = [axes]
                
                scenario_idx = 0
                for scenario_params, repetition_results in all_results.items():
                    if repetition_results:
                        results_per_arrival = repetition_results[0]
                        scenario_label = f"GW:{scenario_params[0]}, Conf:{scenario_params[1]}%, ED:{scenario_params[2]}"
                        
                        # Extract data for this specific scenario
                        scenario_send_times = []
                        scenario_rx1_scheduled = []
                        scenario_rx2_scheduled = []
                        
                        for send_time in sorted(results_per_arrival.keys()):
                            for (g, n), [rx1, rx2] in results_per_arrival[send_time].items():
                                scenario_send_times.append(send_time)
                                scenario_rx1_scheduled.append(1 if rx1 else 0)
                                scenario_rx2_scheduled.append(2 if rx2 else 0)
                        
                        ax = axes[scenario_idx]
                        
                        # Plot RX1 scheduling (blue vertical lines at y=1)
                        rx1_times = [t for t, rx1 in zip(scenario_send_times, scenario_rx1_scheduled) if rx1 == 1]
                        if rx1_times:
                            ax.vlines(rx1_times, 0.9, 1.1, colors='blue', label='RX1 Scheduled', alpha=0.8, linewidth=1.5)
                        
                        # Plot RX2 scheduling (red vertical lines at y=2)
                        rx2_times = [t for t, rx2 in zip(scenario_send_times, scenario_rx2_scheduled) if rx2 == 2]
                        if rx2_times:
                            ax.vlines(rx2_times, 1.9, 2.1, colors='red', label='RX2 Scheduled', alpha=0.8, linewidth=1.5)
                        
                        # Plot unscheduled packets (gray vertical lines at y=0)
                        unscheduled_times = [t for t, rx1, rx2 in zip(scenario_send_times, scenario_rx1_scheduled, scenario_rx2_scheduled) if rx1 == 0 and rx2 == 0]
                        if unscheduled_times:
                            ax.vlines(unscheduled_times, -0.1, 0.1, colors='gray', label='Not Scheduled', alpha=0.8, linewidth=1.5)
                        
                        ax.set_xlabel('Send Time (seconds)')
                        ax.set_ylabel('Scheduling Status')
                        ax.set_title(f"{title} - {scenario_label}")
                        ax.set_yticks([0, 1, 2])
                        ax.set_yticklabels(['Not Scheduled', 'RX1', 'RX2'])
                        ax.set_ylim(-0.3, 2.3)
                        ax.grid(True, alpha=0.3)
                        ax.legend()
                        
                        scenario_idx += 1
                
                plt.tight_layout()
    
    def _extract_results(self, y1, y2,y_coll, Uc_n,ed_sf):
        
        """Extract optimization results"""
        selected_options = []
        scheduled_count = [0, 0]  # [rx1_count, rx2_count]
        half_duplex_loss = 0
        scheduleed_count_per_rx_per_SF = {"rx1":{7:0,8:0,9:0,10:0,11:0,12:0},"rx2":{7:0,8:0,9:0,10:0,11:0,12:0}}
        expected_scheduled = 0
        results_per_arrival = {}
        for n in Uc_n:
            for j, send_time in enumerate(Uc_n[n]):
                tnj_g_list = Uc_n[n][send_time]
                expected_scheduled += 1
                if send_time not in results_per_arrival:
                    results_per_arrival[send_time] = {}
                y_coll_val = pulp.value(y_coll.get((n, j), 0))
                if y_coll_val and y_coll_val > 0.5:
                    half_duplex_loss += 1
                    continue  # Skip this packet as it resulted in a collision due to half-duplex constraint
                for (g, (s_t, e_t)) in tnj_g_list:
                    y1_val = pulp.value(y1.get((g, n, j), 0))
                    y2_val = pulp.value(y2.get((g, n, j), 0))
                    results_per_arrival[send_time][(g,n)] = [0, 0]
                    if y1_val and y1_val > 0.5:
                        scheduleed_count_per_rx_per_SF["rx1"][ed_sf[n]] += 1
                        scheduled_count[0] += 1
                        results_per_arrival[send_time][(g,n)][0] = 1
                    if y2_val and y2_val > 0.5:
                        scheduleed_count_per_rx_per_SF["rx2"][ed_sf[n]] += 1
                        results_per_arrival[send_time][(g,n)][1] = 1
                        scheduled_count[1] += 1
                    
        


        result_summary = {"scheduled_count": scheduled_count,"Rx_sf_distri": scheduleed_count_per_rx_per_SF, "expected_scheduled": expected_scheduled, "%ACK": (scheduled_count[0] + scheduled_count[1]) / expected_scheduled if expected_scheduled > 0 else 0, "Loss_half_duplex%": half_duplex_loss / expected_scheduled if expected_scheduled > 0 else 0}
        return result_summary,results_per_arrival

    def get_cached_toa(self, payload_size, sf):
        """Cached TimeOnAir calculation for performance"""
        key = (payload_size, sf)
        if key not in self.toa_cache:
            self.toa_cache[key] = self.TimeOnAir(payload_size, sf)
            #print(f"Computed ToA for payload {payload_size} and SF {sf}: {self.toa_cache[key]} ms")
        return self.toa_cache[key]
    


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
    
    def compute_duty_cycle_consumption(self, all_results):
        """
        Compute cumulative duty cycle consumption over time for each gateway and receive window
        
        Args:
            all_results: Dictionary with scenario parameters as keys and list of repetition results as values
                         Structure: {(num_gateways, percentage_confirm, num_end_devices): [results_per_arrival, ...]}
            default_rx1_sf: Default spreading factor for RX1 window (used when SF info not available)
            
        Returns:
            Dictionary with structure: {scenario_params: {gateway: {'RX1': [(time, cumulative_dc), ...], 
                                                                   'RX2': [(time, cumulative_dc), ...]}}}
        """
        duty_cycle_results = {}
        for repetition_results in all_results:
            # Take only the first repetition (index 0)
            if not repetition_results:
                continue
                
            results_per_arrival = all_results[repetition_results][0]
            duty_cycle_results = {}
            # Initialize duty cycle tracking for all gateways
            gateway_dc = {}
            sf_ed_scenario = self.SF_ed[repetition_results]
            # Process packets in chronological order
            for send_time in sorted(results_per_arrival.keys()):
                for (g, n), [rx1, rx2] in results_per_arrival[send_time].items():
                    # Initialize gateway tracking if not exists
                    if g not in gateway_dc:
                        gateway_dc[g] = {'RX1': 0.0, 'RX2': 0.0, 'RX1_timeline': [], 'RX2_timeline': []}
                    
                    # Calculate duty cycle consumption for this packet
                    if rx1 == 1:  # Scheduled on RX1
                        # For RX1, use default SF or estimated SF for the end device
                        if n in sf_ed_scenario:
                            sf_for_toa = sf_ed_scenario[n]
                        else:
                            continue
                        toa_rx1_ms = self.get_cached_toa(self.payload_size, sf_for_toa)/1000
                        gateway_dc[g]['RX1'] += toa_rx1_ms
                        
                    if rx2 == 1:  # Scheduled on RX2
                        # For RX2, always use SF=12 as per the constraints
                        toa_rx2_ms = self.get_cached_toa(self.payload_size, 12)/1000
                        gateway_dc[g]['RX2'] += toa_rx2_ms
                    
                    # Record cumulative duty cycle at this time point
                    gateway_dc[g]['RX1_timeline'].append((send_time, gateway_dc[g]['RX1']))
                    gateway_dc[g]['RX2_timeline'].append((send_time, gateway_dc[g]['RX2']))
            
            # Clean up and store results
            for g, dc_data in gateway_dc.items():
                if g not in duty_cycle_results:
                    duty_cycle_results[g] = {}
                
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
                
                duty_cycle_results[g] = {
                    'RX1': rx1_timeline,
                    'RX2': rx2_timeline
                }
        
        return duty_cycle_results
    def compute_statistics(self,results,duty_cycle):

        stats = {
            "ACK%": results["%ACK"],
            "used_rx1_percentage_total": results["scheduled_count"][0] / results["expected_scheduled"] if results["expected_scheduled"] > 0 else 0,
            "used_rx2_percentage_total": results["scheduled_count"][1] / results["expected_scheduled"] if results["expected_scheduled"] > 0 else 0,
            "duty_cycle_monitoring": duty_cycle,        
            "Loss_half_duplex%": results["Loss_half_duplex%"],
            "USE_Rx1_sf7": results["Rx_sf_distri"]["rx1"][7]/(results["Rx_sf_distri"]["rx1"][7] + results["Rx_sf_distri"]["rx2"][7]) if (results["Rx_sf_distri"]["rx1"][7] + results["Rx_sf_distri"]["rx2"][7])>0 else 0,
            "USE_Rx1_sf8": results["Rx_sf_distri"]["rx1"][8]/(results["Rx_sf_distri"]["rx1"][8] + results["Rx_sf_distri"]["rx2"][8]) if (results["Rx_sf_distri"]["rx1"][8] + results["Rx_sf_distri"]["rx2"][8])>0 else 0,
            "USE_Rx1_sf9": results["Rx_sf_distri"]["rx1"][9]/(results["Rx_sf_distri"]["rx1"][9] + results["Rx_sf_distri"]["rx2"][9]) if (results["Rx_sf_distri"]["rx1"][9] + results["Rx_sf_distri"]["rx2"][9])>0 else 0,
            "USE_Rx1_sf10": results["Rx_sf_distri"]["rx1"][10]/(results["Rx_sf_distri"]["rx1"][10] + results["Rx_sf_distri"]["rx2"][10]) if (results["Rx_sf_distri"]["rx1"][10] + results["Rx_sf_distri"]["rx2"][10])>0 else 0,
            "USE_Rx1_sf11": results["Rx_sf_distri"]["rx1"][11]/(results["Rx_sf_distri"]["rx1"][11] + results["Rx_sf_distri"]["rx2"][11]) if (results["Rx_sf_distri"]["rx1"][11] + results["Rx_sf_distri"]["rx2"][11])>0 else 0,
            "USE_Rx1_sf12": results["Rx_sf_distri"]["rx1"][12]/(results["Rx_sf_distri"]["rx1"][12] + results["Rx_sf_distri"]["rx2"][12]) if (results["Rx_sf_distri"]["rx1"][12] + results["Rx_sf_distri"]["rx2"][12])>0 else 0,
            "USE_Rx2_sf7": results["Rx_sf_distri"]["rx2"][7]/(results["Rx_sf_distri"]["rx1"][7] + results["Rx_sf_distri"]["rx2"][7]) if (results["Rx_sf_distri"]["rx1"][7] + results["Rx_sf_distri"]["rx2"][7])>0 else 0,
            "USE_Rx2_sf8":  results["Rx_sf_distri"]["rx2"][8]/(results["Rx_sf_distri"]["rx1"][8] + results["Rx_sf_distri"]["rx2"][8]) if (results["Rx_sf_distri"]["rx1"][8] + results["Rx_sf_distri"]["rx2"][8])>0 else 0,
            "USE_Rx2_sf9":  results["Rx_sf_distri"]["rx2"][9]/(results["Rx_sf_distri"]["rx1"][9] + results["Rx_sf_distri"]["rx2"][9]) if (results["Rx_sf_distri"]["rx1"][9] + results["Rx_sf_distri"]["rx2"][9])>0 else 0,
            "USE_Rx2_sf10": results["Rx_sf_distri"]["rx2"][10]/(results["Rx_sf_distri"]["rx1"][10] + results["Rx_sf_distri"]["rx2"][10]) if (results["Rx_sf_distri"]["rx1"][10] + results["Rx_sf_distri"]["rx2"][10])>0 else 0,
            "USE_Rx2_sf11": results["Rx_sf_distri"]["rx2"][11]/(results["Rx_sf_distri"]["rx1"][11] + results["Rx_sf_distri"]["rx2"][11]) if (results["Rx_sf_distri"]["rx1"][11] + results["Rx_sf_distri"]["rx2"][11])>0 else 0,
            "USE_Rx2_sf12": results["Rx_sf_distri"]["rx2"][12]/(results["Rx_sf_distri"]["rx1"][12] + results["Rx_sf_distri"]["rx2"][12]) if (results["Rx_sf_distri"]["rx1"][12] + results["Rx_sf_distri"]["rx2"][12])>0 else 0,

        }
        return stats
    def plot_duty_cycle_consumption(self, duty_cycle_results, title="Duty Cycle Consumption Over Time"):
        """
        Plot cumulative duty cycle consumption over time with separate scales for RX1 and RX2
        
        Args:
            duty_cycle_results: Output from compute_duty_cycle_consumption()
            title: Plot title
        """
        unique_scenarios = len(duty_cycle_results)
        fig, axes = plt.subplots(unique_scenarios, 1, figsize=(5, 5 * unique_scenarios))
        if unique_scenarios == 1:
            axes = [axes]
        
        scenario_idx = 0
        for scenario_params, gateway_data in duty_cycle_results.items():
            scenario_label = f"GW:{scenario_params[0]}, Conf:{scenario_params[1]}%, ED:{scenario_params[2]}"
            ax1 = axes[scenario_idx]  # Left y-axis for RX1
            ax2 = ax1.twinx()         # Right y-axis for RX2
            #print(gateway_data)
            for gateway, dc_data in gateway_data[0].items():

                # Plot RX1 duty cycle consumption on left y-axis
                if dc_data['RX1']:
                    times_rx1, dc_rx1 = zip(*dc_data['RX1'])
                    ax1.step(times_rx1, dc_rx1, where='post', label=f'GW{gateway} - RX1', 
                           linewidth=2, alpha=0.8, color=f'C{gateway}')
                
                # Plot RX2 duty cycle consumption on right y-axis
                if dc_data['RX2']:
                    times_rx2, dc_rx2 = zip(*dc_data['RX2'])
                    ax2.step(times_rx2, dc_rx2, where='post', label=f'GW{gateway} - RX2', 
                           linewidth=2, alpha=0.8, linestyle='--', color=f'C{gateway}')
            
            # Add duty cycle limits as horizontal lines
            ax1.axhline(y=36, color='blue', linestyle=':', alpha=0.5, label='RX1 Limit (1%)')
            ax2.axhline(y=360, color='red', linestyle=':', alpha=0.5, label='RX2 Limit (10%)')
            
            # Configure left y-axis (RX1)
            ax1.set_xlabel('Send Time (seconds)')
            ax1.set_ylabel('RX1 Cumulative Duty Cycle (ms)', color='blue')
            ax1.tick_params(axis='y', labelcolor='blue')
            ax1.grid(True, alpha=0.3)
            
            # Configure right y-axis (RX2)
            ax2.set_ylabel('RX2 Cumulative Duty Cycle (ms)', color='red')
            ax2.tick_params(axis='y', labelcolor='red')
            
            # Set title
            ax1.set_title(f"{title} - {scenario_label}")
            
            # Combine legends from both axes
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
            
            scenario_idx += 1
        
        plt.tight_layout()
        

# opT_1 = OptimalSchedulling("_Studying prediction/Optimization_files_ad_hoc_min")
# opT_2 = OptimalSchedulling("_Studying prediction/Optimization_files_ad_hoc_min","BUDGET")

# ALL_results_2,dc_results_2,_ = opT_2.run()
# ALL_results,dc_results_1,_ = opT_1.run()

# opT_1.plot_scheduling_results(ALL_results)
# opT_2.plot_scheduling_results(ALL_results_2)
# opT_1.plot_duty_cycle_consumption(dc_results_1)
# opT_2.plot_duty_cycle_consumption(dc_results_2)

#plt.show()