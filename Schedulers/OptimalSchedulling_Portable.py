import os
import pandas as pd
import numpy as np
import pulp 
import math
from io import StringIO


class OptimalSchedulling_Portable():
    def __init__(self,mode,horizon):
        self.toa_cache = {}  # Cache for TimeOnAir calculations
        self.payload_size = 12  # Assuming a fixed payload size for calculations
        self.y1 = None
        self.y2 = None
        self.mode = mode
        self.horizon = horizon

    




    def LIP_problem(self,Uc_n, ed_sf,usable_rx,gw_max_snr,UL_reference ):
        """
        Linear Integer Programming problem for downlink scheduling optimization
        """
        
        
        
        # Create optimization problem and variables
        m = pulp.LpProblem("DownlinkScheduling", pulp.LpMaximize)
        y1 = {}
        y2 = {}
        y_coll = {}
        objective_terms = []
        alpha = 0
        betha = 10e-1
        Gr = []
        order_gw = {gw: (len(gw_max_snr)-idx)*betha for idx, gw in enumerate(gw_max_snr)}
        for n in Uc_n:
            for j, send_time in enumerate(Uc_n[n]):
                tnj_g_list = Uc_n[n][send_time]
                # UL_reference can never collide (it is the frame being scheduled);
                # use a constant 0 instead of a binary variable to reduce problem size.
                if n == UL_reference:
                    y_coll[(n,j)] = 0
                else:
                    y_coll_n_j = pulp.LpVariable(f"ycoll_{n}_{j}", cat='Binary')
                    y_coll[(n,j)] = y_coll_n_j
                for (g, (s_t, e_t)) in tnj_g_list:
                    if g not in Gr:
                        Gr.append(g)         
                    y1_g_n_j = pulp.LpVariable(f"y1_{g}_{n}_{j}", cat='Binary')
                    y2_g_n_j = pulp.LpVariable(f"y2_{g}_{n}_{j}", cat='Binary')
                    y1[(g,n,j)] = y1_g_n_j
                    y2[(g,n,j)] = y2_g_n_j
                    if g not in order_gw or n != UL_reference:
                        gw_prio = 0
                    else:
                        gw_prio = order_gw[g]
                    objective_terms.append(((1+gw_prio)*((1+alpha)*y1_g_n_j + y2_g_n_j)))
                    
        Y_b = {"y1": y1, "y2": y2, "y_coll": y_coll}            
        m += pulp.lpSum(objective_terms)
        
        # Compute overlaps and duty cycle pairs
        overlap_rx1_any, overlap_rx2_any, overlap_ul_with_dl = self._compute_overlaps(Uc_n, ed_sf,Y_b)
        
        dc_rx1_pairs, dc_rx2_pairs = self._compute_duty_cycle_pairs(Uc_n, ed_sf, Y_b, Gr)
        
        # Add all constraints
        # self._add_constraints(m, Y_b, UL_reference, Uc_n, Gr, ed_sf,
        #                     overlap_rx1_any, overlap_rx2_any, 
        #                     overlap_ul_with_dl,
        #                       dc_rx1_pairs, dc_rx2_pairs,usable_rx)
        
        # Add all constraints
        self._add_constraints(m, Y_b, y_coll, Uc_n, Gr, ed_sf,
                            overlap_rx1_any, overlap_rx2_any, 
                            overlap_ul_with_dl,
                              dc_rx1_pairs, dc_rx2_pairs,UL_reference,usable_rx)
        # Solve and extract results
        # Save model to text file before solving
        
        #m.writeLP("model_n.lp")

        # solver = pulp.PULP_CBC_CMD(
        #         msg=0,
        #         timeLimit=60,  # 60 second time limit
        #         gapRel=0.1,   # 5% optimality gap tolerance
        #         threads=4,     # Use multiple threads
        #         options=['presolve on', 'cuts on', 'heuristics on']
        # )
        # m.solve(solver)
        cplex_solver = pulp.CPLEX_CMD(
            msg=0,
            timeLimit=10,
            gapRel=0.2,
            threads=8
        )
        if cplex_solver.available():
            solver = cplex_solver
        else:
            highs = pulp.HiGHS_CMD(msg=0, timeLimit=10, gapRel=0.2, threads=8)
            if highs.available():
                solver = highs
                #print("Using HiGHS solver")
            else:
                solver = pulp.PULP_CBC_CMD(
                    msg=0,
                    timeLimit=10,
                    gapRel=0.2,
                    threads=8,
                )
        m.solve(solver)
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
        self.y1 = y1
        self.y2 = y2
        return self.getresults_raw(Uc_n,UL_reference)
    
    # def _compute_overlaps(self, Uc_n, ed_sf, Y_b):
    #     """Compute overlap relationships between frames"""
    #     overlap_rx1_any = {(g,n,j): [] for (g,n,j) in Y_b["y1"]}
    #     overlap_rx2_any = {(g,n,j): [] for (g,n,j) in Y_b["y1"]}
    #     overlap_ul_with_dl = {(g,n,j): [] for (g,n,j) in Y_b["y1"]}
        
    #     for n in Uc_n:
    #         for j, send_time in enumerate(Uc_n[n]):

    #             for g, (s_t, e_t) in Uc_n[n][send_time]:
    #                 sf_n = ed_sf[n]

    #                 rx1_start, rx1_end = e_t + 1, e_t + 1 + self.get_cached_toa(self.payload_size, sf_n) / 1000
    #                 rx2_start, rx2_end = e_t + 2, e_t + 2 + self.get_cached_toa(self.payload_size, 12) / 1000
    #                 for n_p in Uc_n:
    #                     for j_p,send_time_p in enumerate(Uc_n[n_p]):
    #                         for g_p, (s_t_p, e_t_p) in Uc_n[n_p][send_time_p]:
    #                             if (j,n) == (j_p,n_p) or g!= g_p:
    #                                 continue
                                    
    #                             rx1_start_tp = e_t_p + 1
    #                             sf_tp = ed_sf[n_p]
    #                             rx1_end_tp = rx1_start_tp + self.get_cached_toa(self.payload_size, sf_tp) / 1000
    #                             rx2_start_tp, rx2_end_tp = e_t_p + 2, e_t_p + 2 + self.get_cached_toa(self.payload_size, 12) / 1000
                                
    #                             # Check uplink-downlink overlaps
    #                             if (e_t >= rx1_start_tp and e_t <= rx1_end_tp) :
    #                                 overlap_ul_with_dl[(g,n,j)].append(Y_b["y1"][(g_p,n_p,j_p)])
    #                             if (e_t >= rx2_start_tp and e_t <= rx2_end_tp) :
    #                                 overlap_ul_with_dl[(g,n,j)].append(Y_b["y2"][(g_p,n_p,j_p)])
                                
    #                             # Check downlink-downlink overlaps
    #                             if (rx1_start < rx1_end_tp and rx1_end > rx1_start_tp):
    #                                 overlap_rx1_any[(g,n,j)].append(Y_b["y1"][(g_p,n_p,j_p)])
    #                             if (rx1_start < rx2_end_tp and rx1_end > rx2_start_tp):
    #                                 overlap_rx1_any[(g,n,j)].append(Y_b["y2"][(g_p,n_p,j_p)])
    #                             if (rx2_start < rx1_end_tp and rx2_end > rx1_start_tp):
    #                                 overlap_rx2_any[(g,n,j)].append(Y_b["y1"][(g_p,n_p,j_p)])
    #                             if (rx2_start < rx2_end_tp and rx2_end > rx2_start_tp):
    #                                 overlap_rx2_any[(g,n,j)].append(Y_b["y2"][(g_p,n_p,j_p)])
        
    #     return overlap_rx1_any, overlap_rx2_any, overlap_ul_with_dl
    def _compute_overlaps(self, Uc_n, ed_sf, Y_b):
        overlap_rx1_any = {(g,n,j): [] for (g,n,j) in Y_b["y1"]}
        overlap_rx2_any = {(g,n,j): [] for (g,n,j) in Y_b["y1"]}
        overlap_ul_with_dl = {(g,n,j): [] for (g,n,j) in Y_b["y1"]}

        # Precompute all windows once — O(N*J*G) instead of O(N²*J²*G²)
        windows = {}
        for n in Uc_n:
            for j, send_time in enumerate(Uc_n[n]):
                for g, (s_t, e_t) in Uc_n[n][send_time]:
                    sf = ed_sf[n]
                    toa_sf = self.get_cached_toa(self.payload_size, sf) / 1000
                    toa_12 = self.get_cached_toa(self.payload_size, 12) / 1000
                    windows[(g, n, j)] = {
                        "e_t": e_t,
                        "rx1_start": e_t + 1,
                        "rx1_end":   e_t + 1 + toa_sf,
                        "rx2_start": e_t + 2,
                        "rx2_end":   e_t + 2 + toa_12,
                    }

        # Now the comparison loop just does dictionary lookups
        for (g, n, j), w in windows.items():
            for (g_p, n_p, j_p), w_p in windows.items():
                if (n, j) == (n_p, j_p) or g != g_p:
                    continue

                # Uplink-downlink overlaps
                if w["e_t"] >= w_p["rx1_start"] and w["e_t"] <= w_p["rx1_end"]:
                    overlap_ul_with_dl[(g,n,j)].append(Y_b["y1"][(g_p,n_p,j_p)])
                if w["e_t"] >= w_p["rx2_start"] and w["e_t"] <= w_p["rx2_end"]:
                    overlap_ul_with_dl[(g,n,j)].append(Y_b["y2"][(g_p,n_p,j_p)])

                # Downlink-downlink overlaps
                if w["rx1_start"] < w_p["rx1_end"] and w["rx1_end"] > w_p["rx1_start"]:
                    overlap_rx1_any[(g,n,j)].append(Y_b["y1"][(g_p,n_p,j_p)])
                if w["rx1_start"] < w_p["rx2_end"] and w["rx1_end"] > w_p["rx2_start"]:
                    overlap_rx1_any[(g,n,j)].append(Y_b["y2"][(g_p,n_p,j_p)])
                if w["rx2_start"] < w_p["rx1_end"] and w["rx2_end"] > w_p["rx1_start"]:
                    overlap_rx2_any[(g,n,j)].append(Y_b["y1"][(g_p,n_p,j_p)])
                if w["rx2_start"] < w_p["rx2_end"] and w["rx2_end"] > w_p["rx2_start"]:
                    overlap_rx2_any[(g,n,j)].append(Y_b["y2"][(g_p,n_p,j_p)])

        return overlap_rx1_any, overlap_rx2_any, overlap_ul_with_dl
    def _compute_duty_cycle_pairs(self, Uc_n, ed_sf, Y_b, Gr):
        """Compute duty cycle forbidden pairs using sort-and-sweep — O(N log N) per gateway"""
        G = list(set(Gr))
        dc_rx1_pairs = {g: [] for g in G}
        dc_rx2_pairs = {g: [] for g in G}

        # Collect per-gateway frame list: (s_t, toa_rx1_s, toa_rx2_s, n, j)
        frames_per_gw = {g: [] for g in G}
        for n in Uc_n:
            sf_n = ed_sf[n]
            toa_rx1 = self.get_cached_toa(self.payload_size, sf_n) / 1000
            toa_rx2 = self.get_cached_toa(self.payload_size, 12) / 1000
            for j, send_time in enumerate(Uc_n[n]):
                for g, (s_t, e_t) in Uc_n[n][send_time]:
                    if g in frames_per_gw:
                        frames_per_gw[g].append((s_t, toa_rx1, toa_rx2, n, j))

        for g, frames in frames_per_gw.items():
            frames.sort(key=lambda x: x[0])
            n_frames = len(frames)
            for i in range(n_frames):
                s_t, toa_rx1_i, toa_rx2_i, n_i, j_i = frames[i]
                rx1_window = s_t + 100 * toa_rx1_i
                rx2_window = s_t + 10  * toa_rx2_i
                sweep_end  = max(rx1_window, rx2_window)
                for k in range(i + 1, n_frames):
                    s_t_p, _, _, n_p, j_p = frames[k]
                    if s_t_p >= sweep_end:
                        break  # frames are sorted; nothing beyond this can match
                    if n_p == n_i:
                        continue  # same ED, skip
                    if s_t_p < rx1_window:
                        dc_rx1_pairs[g].append((Y_b["y1"][(g, n_i, j_i)], Y_b["y1"][(g, n_p, j_p)]))
                    if s_t_p < rx2_window:
                        dc_rx2_pairs[g].append((Y_b["y2"][(g, n_i, j_i)], Y_b["y2"][(g, n_p, j_p)]))

        return dc_rx1_pairs, dc_rx2_pairs

    # def _add_constraints(self, m, Y_b, UL_reference, Uc_n, Gr, ed_sf, 
    #                     overlap_rx1_any, overlap_rx2_any, overlap_ul_with_dl, dc_rx1_pairs, dc_rx2_pairs, usable_rx):
    #     """Add all constraints to the optimization model"""
        
    #     # Half-duplex constraints
    #     for (g,n,j), overlaps in overlap_ul_with_dl.items():
    #         half_duplex = overlaps
    #         Gr_n_j_len = len(Uc_n[n][list(Uc_n[n].keys())[j]])
    #         if half_duplex:
    #             # Half-duplex constraint: if there are overlapping transmissions, mark as collision
    #             # This ensures that overlapping uplink and downlink transmissions result in a collision
    #             # Half-duplex constraint: if there are overlapping transmissions, mark as collision
    #             # This ensures that overlapping uplink and downlink transmissions result in a collision
    #             m +=pulp.lpSum(half_duplex) - Gr_n_j_len + 1 <= Y_b["y_coll"][(n,j)],f"HalfDuplex_collision_n{n}_j{j}_g{g}"
        
    #     # Duty-cycle constraints
    #     constrint_n = 0
    #     for g, pairs in dc_rx1_pairs.items():
    #         for y_1_a, y_1_b in pairs:
                
    #             m += y_1_a + y_1_b <= 1, f"DutyCycle_RX1_Constraint_g{g,constrint_n}"
    #             constrint_n+=1
    #     constrint_n = 0
    #     for g, pairs in dc_rx2_pairs.items():
    #         for y_2_a, y_2_b in pairs:
    #             m += y_2_a + y_2_b <= 1, f"DutyCycle_RX2_Constraint_g{g,constrint_n}"
    #             constrint_n+=1
        
    #     # Overlap constraints
    #     for n in Uc_n:
    #         for j, send_time in enumerate(Uc_n[n]):
    #             Y1_Y2_g = []
    #             for g, (s_t, e_t) in Uc_n[n][send_time]:
    #                 # Rx1 and Rx2 overlap constraints
    #                 y1_g_n_j_overlaps = overlap_rx1_any[(g,n,j)]
    #                 y2_g_n_j_overlaps = overlap_rx2_any[(g,n,j)]

    #                 # Mutual exclusion and 
    #                 if y1_g_n_j_overlaps:
    #                     m += Y_b["y1"][(g,n,j)] + pulp.lpSum(y1_g_n_j_overlaps) <= 1, f"Rx1 Overlap Constraint{n}_j{j}_g{g}"
    #                 if y2_g_n_j_overlaps:   
    #                     m += Y_b["y2"][(g,n,j)] + pulp.lpSum(y2_g_n_j_overlaps) <= 1, f"Rx2 Overlap Constraint{n}_j{j}_g{g}"

                    
    #                 Y1_Y2_g.append(Y_b["y1"][(g,n,j)])
    #                 Y1_Y2_g.append(Y_b["y2"][(g,n,j)])
    #                 m += Y_b["y1"][(g,n,j)] + Y_b["y2"][(g,n,j)] <= 1,f"Rx1 or Rx2 Constraint{n}_j{j}_g{g}"
    #                 # if usable_rx[g][0]>e_t+1:
    #                 #     m += Y_b["y1"][(g,n,j)] <=0 ,f"Usable Rx1 Constraint{n}_j{j}_g{g}"
    #                 # if usable_rx[g][1]>e_t+2:
    #                 #     m += Y_b["y2"][(g,n,j)] <=0 ,f"Usable Rx2 Constraint{n}_j{j}_g{g}"

    #                 if usable_rx[g][0]==0 and n == UL_reference:
    #                     m += Y_b["y1"][(g,n,j)] <=0 ,f"Usable Rx1 Constraint{n}_j{j}_g{g}"
    #                 if usable_rx[g][1]==0 and n == UL_reference:
    #                     m += Y_b["y2"][(g,n,j)] <=0 ,f"Usable Rx2 Constraint{n}_j{j}_g{g}"




            

            
    #             m +=pulp.lpSum(Y1_Y2_g) <= 1 - Y_b["y_coll"][(n,j)], f"ACK Only if Received (ED:{n}_j:{j}_g:{g}): "
 
    def _add_constraints(self, m, Y_b, y_coll, Uc_n, Gr, ed_sf, 
                        overlap_rx1_any, overlap_rx2_any, overlap_ul_with_dl, dc_rx1_pairs, dc_rx2_pairs, UL_reference, usable_rx):
        """Add all constraints to the optimization model"""
        # Precompute key lists to avoid repeated list(keys)[j] allocations in the hot loop
        keys_map = {n: list(Uc_n[n].keys()) for n in Uc_n}
        # Half-duplex constraints
        for (g,n,j), overlaps in overlap_ul_with_dl.items():
            half_duplex = overlaps
            Gr_n_j_len = len(Uc_n[n][keys_map[n][j]])
            if half_duplex:
                # Half-duplex constraint: if there are overlapping transmissions, mark as collision
                # This ensures that overlapping uplink and downlink transmissions result in a collision
                # Half-duplex constraint: if there are overlapping transmissions, mark as collision
                # This ensures that overlapping uplink and downlink transmissions result in a collision
                m +=pulp.lpSum(half_duplex) - Gr_n_j_len + 1 <= Y_b["y_coll"][(n,j)],f"HalfDuplex_collision_n{n}_j{j}_g{g}"
        
        # Duty-cycle constraints
        constrint_n = 0

        rx1_terms_gw = {}
        rx2_terms_gw = {}
        for g in Gr:
            rx1_terms = []
            rx2_terms = []
            for n in Uc_n:
                for j, send_time in enumerate(Uc_n[n]):
                    for g_p, (s_t_p, e_t_p) in Uc_n[n][send_time]:
                        if g_p != g:
                            continue
                        # ISSUE: Current approach has scaling problems
                        # rx1_terms.append(Y_b["y1"][(g,n,j)] * round(self.get_cached_toa(self.payload_size, ed_sf[n])/36))
                        # rx2_terms.append(Y_b["y2"][(g,n,j)] * round(self.get_cached_toa(self.payload_size, 12)/360 ))
                        
                        # CORRECTED: Proper duty cycle constraint formulation
                        # Option 1: Direct time-based constraints (in milliseconds)
                        toa_rx1_ms = self.get_cached_toa(self.payload_size, ed_sf[n])
                        toa_rx2_ms = self.get_cached_toa(self.payload_size, 12)
                        
                        # For 1% duty cycle over 1 hour = 36,000 ms budget
                        # For 10% duty cycle over 1 hour = 360,000 ms budget
                        rx1_terms.append(Y_b["y1"][(g,n,j)] * toa_rx1_ms)
                        rx2_terms.append(Y_b["y2"][(g,n,j)] * toa_rx2_ms)

            rx1_terms_gw[g] = rx1_terms
            rx2_terms_gw[g] = rx2_terms
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
                if rx2_terms_gw[g]:
                    # Debug: Print constraint details before adding
                    #print(f"Adding RX2 constraint for gateway {g}: {len(rx2_terms)} terms")
                    # Proper duty cycle limit: 10% of 1 hour = 360,000 ms
                    constraint_rx2 = pulp.lpSum(rx2_terms_gw[g]) <= 360000  # milliseconds
                    m.addConstraint(constraint_rx2, name=f"Rx2_Budget_Constraint_g{g}_n{constrint_n}")
                    constrint_n += 1
        
        elif self.mode == 'budget':


            for g in Gr:               
                if rx1_terms_gw[g]:
                    # Debug: Print constraint details before adding
                    #print(f"Adding RX1 constraint for gateway {g}: {len(rx1_terms)} terms")
                    # Proper duty cycle limit: 1% of 1 hour = 36,000 ms
                    constraint_rx1 = pulp.lpSum(rx1_terms_gw[g]) <= self.horizon*1000*0.01  # milliseconds
                    m.addConstraint(constraint_rx1, name=f"Rx1_Budget_Constraint_g{g}_n{constrint_n}")
                    constrint_n += 1
                    
                if rx2_terms_gw[g]:
                    # Debug: Print constraint details before adding
                    #print(f"Adding RX2 constraint for gateway {g}: {len(rx2_terms)} terms")
                    # Proper duty cycle limit: 10% of 1 hour = 360,000 ms
                    constraint_rx2 = pulp.lpSum(rx2_terms_gw[g]) <= self.horizon*1000*0.1  # milliseconds
                    m.addConstraint(constraint_rx2, name=f"Rx2_Budget_Constraint_g{g}_n{constrint_n}")
                    constrint_n += 1
        else:
            raise ValueError(f"Unknown mode: {self.mode}")


        
        # # Overlap constraints
        # for n in Uc_n:
        #     for j, send_time in enumerate(Uc_n[n]):
        #         Y1_Y2_g = []
        #         for g, (s_t, e_t) in Uc_n[n][send_time]:
        #             # Rx1 and Rx2 overlap constraints
        #             y1_g_n_j_overlaps = overlap_rx1_any[(g,n,j)]
        #             y2_g_n_j_overlaps = overlap_rx2_any[(g,n,j)]

        #             # Mutual exclusion and 
        #             if y1_g_n_j_overlaps:
        #                 m += Y_b["y1"][(g,n,j)] + pulp.lpSum(y1_g_n_j_overlaps) <= 1, f"Rx1 Overlap Constraint{n}_j{j}_g{g}"
        #             if y2_g_n_j_overlaps:   
        #                 m += Y_b["y2"][(g,n,j)] + pulp.lpSum(y2_g_n_j_overlaps) <= 1, f"Rx2 Overlap Constraint{n}_j{j}_g{g}"

                    
        #             Y1_Y2_g .append(Y_b["y1"][(g,n,j)])
        #             Y1_Y2_g .append(Y_b["y2"][(g,n,j)])
        #             m += Y_b["y1"][(g,n,j)] + Y_b["y2"][(g,n,j)] <= 1,f"Rx1 or Rx2 Constraint{n}_j{j}_g{g}"
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

                    
                    Y1_Y2_g.append(Y_b["y1"][(g,n,j)])
                    Y1_Y2_g.append(Y_b["y2"][(g,n,j)])
                    m += Y_b["y1"][(g,n,j)] + Y_b["y2"][(g,n,j)] <= 1,f"Rx1 or Rx2 Constraint{n}_j{j}_g{g}"
                    # if usable_rx[g][0]>e_t+1:
                    #     m += Y_b["y1"][(g,n,j)] <=0 ,f"Usable Rx1 Constraint{n}_j{j}_g{g}"
                    # if usable_rx[g][1]>e_t+2:
                    #     m += Y_b["y2"][(g,n,j)] <=0 ,f"Usable Rx2 Constraint{n}_j{j}_g{g}"

                    if usable_rx[g][0]==0 and n == UL_reference:
                        m += Y_b["y1"][(g,n,j)] <=0 ,f"Usable Rx1 Constraint{n}_j{j}_g{g}"
                    if usable_rx[g][1]==0 and n == UL_reference:
                        m += Y_b["y2"][(g,n,j)] <=0 ,f"Usable Rx2 Constraint{n}_j{j}_g{g}"
                # y_coll is 0 (constant) for UL_reference — no constraint needed
                if n != UL_reference:
                    m += pulp.lpSum(Y1_Y2_g) <= 1 - Y_b["y_coll"][(n,j)], f"ACK Only if Received (ED:{n}_j:{j}_g:{g}): "
                else:
                    m += pulp.lpSum(Y1_Y2_g) <= 1, f"ACK Only if Received (ED:{n}_j:{j}_g:{g}): "
    def getresults_raw(self,Uc_n,ed_in):
        options = []
        for j, send_time in enumerate(Uc_n[ed_in]):
                tnj_g_list = Uc_n[ed_in][send_time]
                for (g, (s_t, e_t)) in tnj_g_list:
                    y1_val = pulp.value(self.y1.get((g, ed_in, j), 0))
                    y2_val = pulp.value(self.y2.get((g, ed_in, j), 0))
                    
                    if y1_val and y1_val > 0.5:
                        options.append((g,0))
                    if y2_val and y2_val > 0.5:
                        options.append((g,1))
        return options

    def extract_results(self, Uc_n):
        """Extract optimization results"""
        selected_options = []
        scheduled_count = [0, 0]  # [rx1_count, rx2_count]
        expected_scheduled = 0
        results_str = []
        for n in Uc_n:
            for j, send_time in enumerate(Uc_n[n]):
                tnj_g_list = Uc_n[n][send_time]
                expected_scheduled += 1
                for (g, (s_t, e_t)) in tnj_g_list:
                    y1_val = pulp.value(self.y1.get((g, n, j), 0))
                    y2_val = pulp.value(self.y2.get((g, n, j), 0))
                    
                    if y1_val and y1_val > 0.5:
                        scheduled_count[0] += 1
                        results_str.append(f"RX1: n={n}, j={j}, g={g}, value={y1_val}")
                    if y2_val and y2_val > 0.5:
                        scheduled_count[1] += 1
                        results_str.append(f"RX2: n={n}, j={j}, g={g}, value={y2_val}")
        
        results_string = "\n".join(results_str)
        

        


        
        return results_string

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

