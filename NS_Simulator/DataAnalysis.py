import numpy as np
import pandas as pd
from collections import OrderedDict
import seaborn as sns
import os

import matplotlib.pyplot as plt

class DataAnalysis:
    def __init__(self, directory=None, name_figures="figures"):
        self.OutputTable = {}
        self.color = {}
        self.directory = directory  # Default directory for CSV files
        self.name_figures = name_figures

    def add_data_outputTable(self,scheduler, param,statistics,color=None):
        if scheduler not in self.OutputTable:
            self.OutputTable[scheduler] = {}
        stats_temp = statistics
        if param not in self.OutputTable[scheduler]:
            self.OutputTable[scheduler][param] = {}
            if color is not None:
                self.color[scheduler] = color
            for key, value in stats_temp.items():
                self.OutputTable[scheduler][param][key] = [value]
        else:
            for key, value in stats_temp.items():
                self.OutputTable[scheduler][param][key].append(value)

    def sort_outputTable(self, order):
        # Map short names to tuple indices
        order_map = {'ed': 0, 'gw': 1, 'p': 2, 'pe': 3}
        # Build the sort key indices from the input order string
        sort_indices = [order_map[o] for o in order.split(',') if o in order_map]

        # Sort the OutputTable keys based on the specified order
        for scheduler_data in self.OutputTable:
            sorted_items = sorted(
                self.OutputTable[scheduler_data].items(),
                key=lambda item: tuple(item[0][i] for i in sort_indices)
            )

            # Rebuild OutputTable as an OrderedDict to preserve order
            self.OutputTable[scheduler_data] = OrderedDict(sorted_items)

    def plot_ack_percentages_by_sf(self, metric_prefix='ACK_sf',thres = 100, title = "",label="ACK%"):
        """
        Plots a heatmap for each scheduler as a subplot in a single row:
        - Y axis: scenario (parameter tuple)
        - X axis: spreading factor (SF7 to SF12)
        - Color: mean ACK% for that scenario and SF
        All schedulers are shown in the same figure with a shared colorbar.
        """
        # Backward-compatible guard: if caller passes title as 2nd positional arg,
        # it lands in `thres` and causes seaborn/matplotlib vmax conversion errors.
        if isinstance(thres, str):
            if title == "":
                title = thres
            thres = 100

        try:
            vmax_value = float(thres)
        except (TypeError, ValueError):
            vmax_value = 100.0

        sf_range = range(7, 13)  # SF7 to SF12
        schedulers = list(self.OutputTable.keys())
        num_sched = len(schedulers)
        
        if num_sched == 0:
            print("No schedulers found in OutputTable.")
            return

        # Prepare heatmap data for each scheduler
        heatmap_data_list = []
        scenario_keys_list = []
        for scheduler in schedulers:
            scenario_keys = sorted(self.OutputTable[scheduler].keys())
            scenario_keys_list.append(scenario_keys)
            heatmap_data = []
            for scenario in scenario_keys:
                row = []
                stats = self.OutputTable[scheduler][scenario]
                for sf in sf_range:
                    metric = f"{metric_prefix}{sf}"
                    ack_list = stats.get(metric, [])
                    ack_mean = np.mean(ack_list) * 100 if ack_list else np.nan
                    row.append(ack_mean)
                heatmap_data.append(row)
            heatmap_data_list.append(np.array(heatmap_data).T)

        # Set up subplots in a single row
        max_scenarios = max(len(keys) for keys in scenario_keys_list)
        subplot_width = max(2.0, max_scenarios * 0.25)
        fig, axes = plt.subplots(
            1, num_sched,
            figsize=(subplot_width * num_sched + 0.8, subplot_width),
            squeeze=False
        )

        for idx, scheduler in enumerate(schedulers):
            ax = axes[0, idx]
            heatmap_array = heatmap_data_list[idx]
            annot_labels = np.where(np.isnan(heatmap_array), '', np.round(heatmap_array).astype(int).astype(str))
            
            sns.heatmap(
            heatmap_array,
            annot=annot_labels,
            fmt="",
            cmap="coolwarm",
            xticklabels=[str(s) for s in scenario_keys_list[idx]],
            yticklabels=[f"SF{sf}" for sf in sf_range],
            cbar=(idx == num_sched - 1),  # Only show colorbar on the last plot
            cbar_kws={'label': label} if idx == num_sched - 1 else {},
            ax=ax,
            vmin=0, vmax=vmax_value,
            annot_kws={"size": 6}
            )
            ax.set_title(f'{title} - {scheduler}', fontsize=10)
            ax.set_xlabel('Scenario', fontsize=12)
            ax.set_ylabel('SF' if idx == 0 else '', fontsize=12)
            ax.set_yticklabels([f"SF{sf}" for sf in sf_range], fontsize=9, rotation=0)
            ax.set_xticklabels([str(s) for s in scenario_keys_list[idx]], fontsize=9, rotation=45, ha='right')

        plt.tight_layout()
        filepath = os.path.join(self.directory, f"{self.name_figures}_ack_percentages_by_sf_{metric_prefix}.pdf") if self.directory else f"{self.name_figures}_ack_percentages_by_sf_{metric_prefix}.pdf"
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        plt.savefig(filepath, format='pdf', bbox_inches='tight')
    def print_all_reports(self, csv_dir=None, filename="all_schedulers_report.csv"):
        # Collect all unique statistic keys for consistent column order
        all_keys = set()
        param_list = []
        rows = []
        schedulers = []
        for scheduler in self.OutputTable:
            for param, stats in self.OutputTable[scheduler].items():
                all_keys.update(stats.keys())
        # Do not sort all_keys; keep insertion order
        all_keys = list(all_keys)

        # Prepare rows for DataFrame
        for scheduler in self.OutputTable:
            for param, stats in self.OutputTable[scheduler].items():
                row = {key: f"{np.mean(stats.get(key, [np.nan]))*100:.2f}" for key in all_keys}
                if isinstance(param, (tuple, list)):
                    param_values = list(param)
                else:
                    param_values = [param]
                param_list.append(param_values)
                rows.append(row)
                schedulers.append(scheduler)

        param_col_names = ['End Devices', 'Gateways', 'Percentage', 'Period']
        df_params = pd.DataFrame(param_list, columns=param_col_names)
        df_stats = pd.DataFrame(rows, columns=all_keys)
        df = pd.concat([pd.Series(schedulers, name='Scheduler'), df_params, df_stats], axis=1)

        # Print as CSV
        if csv_dir:
            os.makedirs(csv_dir, exist_ok=True)  # Ensure directory exists
            filepath = os.path.join(csv_dir, filename)
        else:
            filepath = filename
        df.to_csv(filepath, index=False)
        print(f"Combined report for all schedulers saved to {filepath}")

    def plot_ack_percentages_by_param(self, split_param='gw', metric='ACK%',limit=100,label = "ACK%",scale = 100.0,lm_inf=0.0):
        """
        Plots mean metric per scenario and scheduler with asymmetric min/max error bars.
        Note: these are min/max ranges, not statistical confidence intervals.
        """
        param_index_map = {'ed': 0, 'gw': 1, 'p': 2, 'pe': 3}
        if split_param not in param_index_map:
            return

        idx = param_index_map[split_param]

        split_values = set()
        for scheduler in self.OutputTable:
            for param in self.OutputTable[scheduler]:
                if isinstance(param, (tuple, list)) and len(param) > idx:
                    split_values.add(param[idx])
                elif idx == 0:
                    split_values.add(param)
        split_values = sorted(split_values)

        schedulers = list(self.OutputTable.keys())

        for split_val in split_values:
            scenario_keys = set()
            for scheduler in self.OutputTable:
                for param in self.OutputTable[scheduler]:
                    if (isinstance(param, (tuple, list)) and len(param) > idx and param[idx] == split_val) or \
                       (not isinstance(param, (tuple, list)) and idx == 0 and param == split_val):
                        scenario_keys.add(param)
            scenario_keys = sorted(scenario_keys)

            if not scenario_keys:
                continue

            ack_matrix = []
            ack_min_matrix = []
            ack_max_matrix = []

            for scheduler in schedulers:
                ack_per_scenario = []
                ack_min_per_scenario = []
                ack_max_per_scenario = []

                for scenario in scenario_keys:
                    stats = self.OutputTable[scheduler].get(scenario, {})
                    ack_list = stats.get(metric, [])
                    if ack_list:
                        vals = np.array(ack_list, dtype=float) * scale
                        ack_per_scenario.append(np.mean(vals))
                        ack_min_per_scenario.append(np.min(vals))
                        ack_max_per_scenario.append(np.max(vals))
                    else:
                        ack_per_scenario.append(np.nan)
                        ack_min_per_scenario.append(np.nan)
                        ack_max_per_scenario.append(np.nan)

                ack_matrix.append(np.array(ack_per_scenario, dtype=float))
                ack_min_matrix.append(np.array(ack_min_per_scenario, dtype=float))
                ack_max_matrix.append(np.array(ack_max_per_scenario, dtype=float))

            n_sched = max(len(schedulers), 1)
            bar_width = 0.6         # width of a single bar in data units
            gap_fraction = 0.1        # gap between groups as a fraction of the group width
            group_width = bar_width * n_sched
            group_spacing = group_width * (1 + gap_fraction)
            width = bar_width

            x = np.arange(len(scenario_keys)) * group_spacing

            inches_per_group = group_spacing * 0.25   # tune this to taste
            fig_width = max(5, len(scenario_keys) * inches_per_group)
            fig, ax = plt.subplots(figsize=(fig_width, 5))
            ax.grid(True, linestyle='-', linewidth=1, alpha=0.3, color='gray', zorder=0)

            for i, scheduler in enumerate(schedulers):
                means = ack_matrix[i]
                mins = ack_min_matrix[i]
                maxs = ack_max_matrix[i]

                # centered groups
                positions = x + (i - (len(schedulers) - 1) / 2.0) * width
                valid = ~np.isnan(means)

                if not np.any(valid):
                    continue

                bar_color = self.color.get(scheduler, None)
                ax.bar(
                    positions[valid],
                    means[valid],
                    width * 0.9,
                    label=scheduler,
                    edgecolor='black',
                    linewidth=1.0,
                    color=bar_color,
                    zorder=2
                )

                lower_err = np.maximum(0, means[valid] - mins[valid])
                upper_err = np.maximum(0, maxs[valid] - means[valid])

                ax.errorbar(
                    positions[valid],
                    means[valid],
                    yerr=np.vstack([lower_err, upper_err]),
                    fmt='none',
                    ecolor='black',
                    elinewidth=1.3,
                    capsize=4,
                    zorder=3
                )

            # Tighten horizontal margins so bars are closer to the y-axis and right edge
            half_group = ((n_sched - 1) / 2.0) * width + (width * 0.9) / 2.0
            side_pad = width * 0.15
            ax.set_xlim(x[0] - half_group - side_pad, x[-1] + half_group + side_pad)

            ax.set_ylabel(f'Average {label}', fontsize=16, labelpad=10)
            ax.set_xlabel('(ED,GW,CT,P)', fontsize=16)
            ax.set_xticks(x)
            ax.set_xticklabels([str(s) for s in scenario_keys], rotation=45, ha='right', fontsize=16)
            ax.set_ylim(lm_inf, limit)
            ax.set_yticks(np.linspace(lm_inf, limit, 11))
            ax.set_yticklabels([f"{tick:.1f}".rstrip('0').rstrip('.') for tick in np.linspace(lm_inf, limit, 11)], fontsize=16)
            ax.legend(bbox_to_anchor=(0.5, 1.05), loc='lower center', borderaxespad=0.0, ncol=4,fontsize=12)
            safe_metric = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(metric))
            safe_split = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(split_val))
            save_dir = self.directory if self.directory else "."
            os.makedirs(save_dir, exist_ok=True)
            filename = f"{self.name_figures}_ack_percentages_by_param_{split_param}_{safe_split}_{safe_metric}.pdf"
            fig.subplots_adjust(left=0.14)
            #fig.tight_layout()
            fig.savefig(os.path.join(save_dir, filename), format="pdf", bbox_inches="tight", pad_inches=0.15)


    def plot_duty_cycle_consumption(self, title="Duty Cycle Consumption Over Time", split_param='gw', metric='ACK%'):
        """
        Plot cumulative duty cycle consumption over time with separate scales for RX1 and RX2
        
        Args:
            title: Plot title
            split_param: Parameter to split by ('ed', 'gw', 'p', 'pe')
            metric: Metric name (used for filename)
        """
        param_index_map = {'ed': 0, 'gw': 1, 'p': 2, 'pe': 3}
        if split_param not in param_index_map:
            return

        idx = param_index_map[split_param]
        
        # Extract unique split values
        split_values = set()
        for scheduler in self.OutputTable:
            for param in self.OutputTable[scheduler]:
                if isinstance(param, (tuple, list)) and len(param) > idx:
                    split_values.add(param[idx])
                elif idx == 0:
                    split_values.add(param)
        split_values = sorted(split_values)
        
        duty_cycle_results_schedulers = self.OutputTable
        
        for scheduler in duty_cycle_results_schedulers:
            for split_val in split_values:
                duty_cycle_results_scenario = {
                    param: data for param, data in duty_cycle_results_schedulers[scheduler].items()
                    if (isinstance(param, (tuple, list)) and len(param) > idx and param[idx] == split_val) or
                       (not isinstance(param, (tuple, list)) and idx == 0 and param == split_val)
                }
                
                if not duty_cycle_results_scenario:
                    continue
                
                unique_scenarios = len(duty_cycle_results_scenario)
                max_cols = 4
                ncols = min(unique_scenarios, max_cols)
                nrows = (unique_scenarios + ncols - 1) // ncols
                
                # Calculate figure size based on number of subplots
                subplot_size = 4.0
                fig_width = max(subplot_size, subplot_size * ncols)
                fig_height = max(subplot_size, subplot_size * nrows)
                fig, axes = plt.subplots(nrows, ncols, figsize=(fig_width, fig_height))
                
                if nrows == 1 and ncols == 1:
                    axes = [[axes]]
                elif nrows == 1:
                    axes = [[ax for ax in axes]]
                elif ncols == 1:
                    axes = [[ax] for ax in axes]
                
                scenario_idx = 0
                for scenario_params in duty_cycle_results_scenario:
                    gateway_data = duty_cycle_results_scenario[scenario_params]["duty_cycle_monitoring"][0]
                    scenario_label = f"GW:{scenario_params[1]}, Conf:{scenario_params[2]}%, ED:{scenario_params[0]}"
                    
                    row = scenario_idx // ncols
                    col = scenario_idx % ncols
                    ax1 = axes[row][col]
                    ax2 = ax1.twinx()
                    ax1.set_box_aspect(1)
                    
                    for gateway, dc_data in gateway_data.items():
                        if dc_data['RX1']:
                            times_rx1, dc_rx1 = zip(*dc_data['RX1'])
                            ax1.step(times_rx1, dc_rx1, where='post', label=f'GW{gateway} - RX1', 
                                linewidth=2, alpha=0.8, color=f'C{gateway}')
                        
                        if dc_data['RX2']:
                            times_rx2, dc_rx2 = zip(*dc_data['RX2'])
                            ax2.step(times_rx2, dc_rx2, where='post', label=f'GW{gateway} - RX2', 
                                linewidth=2, alpha=0.8, linestyle='--', color=f'C{gateway}')
                    
                    ax1.axhline(y=36, color='blue', linestyle=':', alpha=0.5, label='RX1 Limit (1%)')
                    ax2.axhline(y=360, color='red', linestyle=':', alpha=0.5, label='RX2 Limit (10%)')
                    
                    if row == nrows - 1:
                        ax1.set_xlabel('Time (s)', fontsize=10)
                        ax1.tick_params(axis='x', labelsize=8)
                    else:
                        ax1.set_xlabel('')
                        ax1.tick_params(axis='x', labelbottom=False)
                    #ax1.set_xlim(0, 3600)
                    
                    ax1.set_ylabel('RX1 DC (s)', color='blue', fontsize=10, labelpad=10)
                    ax1.tick_params(axis='y', labelcolor='blue', labelsize=8)
                    ax1.grid(True, alpha=0.3)
                    
                    ax2.set_ylabel('RX2 DC (s)', color='red', fontsize=10, labelpad=10)
                    ax2.tick_params(axis='y', labelcolor='red', labelsize=8)
                    
                    ax1.set_title(f"{scenario_label}")
                    
                    if row == nrows - 1:
                        lines1, labels1 = ax1.get_legend_handles_labels()
                        lines2, labels2 = ax2.get_legend_handles_labels()
                        ax1.legend(lines1 + lines2, labels1 + labels2, 
                                    bbox_to_anchor=(0.5, -0.25), loc='upper center', 
                                    fontsize=10, ncol=2)
                    scenario_idx += 1
                
                for idx_unused in range(unique_scenarios, nrows * ncols):
                    row = idx_unused // ncols
                    col = idx_unused % ncols
                    fig.delaxes(axes[row][col])
                
                safe_metric = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(metric))
                safe_split = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(split_val))
                safe_scheduler = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(scheduler))
                save_dir = self.directory if self.directory else "."

                os.makedirs(save_dir, exist_ok=True)
                filename = f"{self.name_figures}_duty_cycle_{safe_scheduler}_{split_param}_{safe_split}_{safe_metric}.pdf"
                plt.tight_layout()

                plt.savefig(os.path.join(save_dir, filename), format="pdf", bbox_inches="tight")
                fig.suptitle(f"{title} - {scheduler} ({split_param}={split_val})")

    def plot_ack_heatmap_by_param(self, split_param='gw', metric='ACK%',percentage=100,not_100=False,lm_inf = 0):
        """
        Plots a heatmap for each unique value of the chosen parameter:
        - X axis: scenario (parameter tuple)
        - Y axis: scheduler
        - Color: mean value of the metric for that scenario and scheduler
        - Frames the highest metric value per scenario (column) in green.
        """
        param_index_map = {'ed': 0, 'gw': 1, 'p': 2, 'pe': 3}
        if split_param not in param_index_map:
            return

        idx = param_index_map[split_param]
        split_values = set()
        for scheduler in self.OutputTable:
            for param in self.OutputTable[scheduler]:
                if isinstance(param, (tuple, list)) and len(param) > idx:
                    split_values.add(param[idx])
                elif idx == 0:
                    split_values.add(param)
        split_values = sorted(split_values)
        
        # Filter out "Optimal" scheduler if metric is "CPSR"
        schedulers = list(self.OutputTable.keys())
        if metric == "CPSR":
            schedulers = [s for s in schedulers if s != "Optimal"]

        for split_val in split_values:
            scenario_keys = set()
            for scheduler in schedulers:
                for param in self.OutputTable[scheduler]:
                    if (isinstance(param, (tuple, list)) and len(param) > idx and param[idx] == split_val) or \
                        (not isinstance(param, (tuple, list)) and idx == 0 and param == split_val):
                        scenario_keys.add(param)
            scenario_keys = sorted(scenario_keys)

            # Build heatmap data: rows=schedulers, columns=scenarios
            heatmap_data = []
            for scheduler in schedulers:
                row = []
                for scenario in scenario_keys:
                    stats = self.OutputTable[scheduler].get(scenario, {})
                    metric_list = stats.get(metric, [])
                    if metric_list:
                        metric_mean = np.mean(metric_list) * percentage
                    else:
                        metric_mean = np.nan
                    row.append(metric_mean)
                heatmap_data.append(row)

            heatmap_array = np.array(heatmap_data)
            plt.figure(figsize=(max(5, len(scenario_keys)*0.7), max(3.5, len(schedulers)*0.5)))
            annot_labels = np.where(np.isnan(heatmap_array), '', np.round(heatmap_array).astype(int).astype(str))
            vmax_value = 100 if not_100 == False else np.nanmax(heatmap_array)
            # Choose annotation format: 0 decimals if percentage==100, else 2 decimals
            if percentage == 100:
                annot_labels = np.where(np.isnan(heatmap_array), '', np.round(heatmap_array).astype(int).astype(str))
            else:
                annot_labels = np.where(np.isnan(heatmap_array), '', np.round(heatmap_array, 2).astype(str))

            ax = sns.heatmap(
                heatmap_array,
                annot=annot_labels,
                fmt="",
                cmap="coolwarm",
                xticklabels=[str(s) for s in scenario_keys],
                yticklabels=schedulers,
                cbar_kws={'label': metric},
                vmin=lm_inf, vmax=vmax_value,
                annot_kws={"size": 7}
            )

            # Make y tick labels horizontal
            ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=8, va='center')

            plt.title(f'{metric} by Scenario and Scheduler (split {split_param}={split_val})')
            plt.xlabel('Scenario')
            plt.ylabel('Scheduler')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()

            # Highlight the highest metric value per scenario (column) with a green rectangle,
            # excluding the "Optimal" scheduler from the comparison
            valid_scheduler_indices = [i for i, scheduler in enumerate(schedulers) if scheduler != "Optimal"]

            for j in range(heatmap_array.shape[1]):
                if not valid_scheduler_indices:
                    continue

                col = heatmap_array[valid_scheduler_indices, j]
                if np.all(np.isnan(col)):
                    continue

                max_value = np.nanmax(col)
                max_indices_local = np.where(col == max_value)[0]
                max_indices = [valid_scheduler_indices[idx] for idx in max_indices_local]

                for i in max_indices:
                    ax.add_patch(plt.Rectangle(
                        (j, i), 1, 1, fill=False, edgecolor='limegreen', lw=2, clip_on=False
                    ))
        safe_metric = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(metric))
        safe_split = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in str(split_val))
        save_dir = self.directory if self.directory else "."
        os.makedirs(save_dir, exist_ok=True)

        filename = f"{self.name_figures}_ack_heatmap_by_param_{split_param}_{safe_split}_{safe_metric}.pdf"
        plt.savefig(os.path.join(save_dir, filename), format="pdf", bbox_inches="tight")

    def plot_ack_heatmap_by_param_separated(self, split_param='gw', metric='ACK%', percentage=100, not_100=False):
        """
        Plots a separate figure for each scheduler showing heatmap:
        - X axis: end devices (ed)
        - Y axis: gateways (gw)
        - Color: mean value of the metric
        """
        schedulers = list(self.OutputTable.keys())
        
        # Collect all unique ed and gw values
        ed_values = set()
        gw_values = set()
        
        for scheduler in schedulers:
            for param in self.OutputTable[scheduler]:
                if isinstance(param, (tuple, list)) and len(param) >= 2:
                    ed_values.add(param[0])
                    gw_values.add(param[1])
        
        ed_values = sorted(ed_values)
        gw_values = sorted(gw_values)
        
        # Create one figure per scheduler
        for scheduler in schedulers:
            fig, ax = plt.subplots(figsize=(3.5, 2.5), sharey=True)
            
            # Build heatmap data for this scheduler
            heatmap_data = []
            for gw in gw_values:
                row_data = []
                for ed in ed_values:
                    scenario = None
                    for param in self.OutputTable[scheduler]:
                        if isinstance(param, (tuple, list)) and len(param) >= 2:
                            if param[0] == ed and param[1] == gw:
                                scenario = param
                                break
                    
                    if scenario:
                        stats = self.OutputTable[scheduler].get(scenario, {})
                        metric_list = stats.get(metric, [])
                        metric_mean = np.mean(metric_list) * percentage if metric_list else np.nan
                    else:
                        metric_mean = np.nan
                    row_data.append(metric_mean)
                heatmap_data.append(row_data)
            
            heatmap_array = np.array(heatmap_data)
            
            if percentage == 100:
                annot_labels = np.where(np.isnan(heatmap_array), '', np.round(heatmap_array).astype(int).astype(str))
            else:
                annot_labels = np.where(np.isnan(heatmap_array), '', np.round(heatmap_array, 2).astype(str))
            
            vmax_value = 100 if not not_100 else np.nanmax(heatmap_array)
            
            sns.heatmap(
                heatmap_array,
                annot=annot_labels,
                fmt="",
                cmap="coolwarm",
                xticklabels=[str(ed) for ed in ed_values],
                yticklabels=[str(gw) for gw in gw_values],
                cbar_kws={'label': metric},
                vmin=0, vmax=vmax_value,
                annot_kws={"size": 10},
                ax=ax
            )
            
            ax.set_title(f'{metric}', fontsize=14)
            ax.set_xlabel('End Devices', fontsize=12)
            ax.set_ylabel('Gateways', fontsize=12)
            plt.savefig(f"Figures_holder/{scheduler}_Combined_{'_'.join(metric).replace(' ', '_').replace('%', '')}.pdf")

            plt.tight_layout()
