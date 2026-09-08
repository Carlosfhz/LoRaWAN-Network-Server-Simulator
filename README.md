# Network-Server-Simulator

A Python simulator for evaluating LoRaWAN network-server downlink scheduling strategies. The project models end devices, gateways, channels, uplink traffic, downlink scheduling, duty-cycle restrictions, collisions, half-duplex losses, packet delivery, and energy-related statistics.

The repository includes heuristic schedulers and an optimization-based scheduler so their performance can be compared on the same uplink traces.

## Project Structure

```text
Network-Server-Simulator/
├── FINAL_ALL_SCHEDULER_COMPARISON.py   # Main comparison and plotting script
├── MainTestHeuristicApproeach.py       # Heuristic-scheduler experiments
├── justTrad.py                         # Traditional-scheduler experiments
├── NS_Simulator/                       # Core simulator package
│   ├── Channel.py                      # Path-loss and channel calculations
│   ├── DataAnalysis.py                 # Statistics, tables, and plots
│   ├── EndDevice.py                    # End-device model
│   ├── Frame.py                        # Uplink/downlink frame model
│   ├── LoRaGateway.py                  # Gateway model and downlink queue
│   ├── NetworkServer.py                # Gateway/device registration and scheduling
│   ├── PacketLogger.py                 # Simulation metrics and logs
│   ├── Scheduler.py                    # Base scheduler behavior
│   ├── SimulatorCore.py                # Main simulation loop
│   └── TrafficGeneration.py            # CSV parsing and traffic creation
├── Schedulers/                         # Scheduling implementations
│   ├── SchedulerTraditional.py
│   ├── TraditionalThreshold.py
│   ├── DutyCyleControl.py
│   ├── SchedulerBudgetGreedyEntropy_RSSI_v2.py
│   ├── GreedyFuture.py
│   ├── GreedyFuture_Rolling_Horizon_complete_v3.py
│   ├── OptimalSchedulling.py           # Global MILP scheduler
│   └── OptimalSchedulling_Portable.py  # Rolling-horizon optimization helper
├── Logs-Test/                          # Input uplink traces
├── OUTPUT_IMAGES/                      # Generated plots
└── RESULTS_OPTIMAL_*.json              # Cached optimization results
```

The `__init__.py` files make `NS_Simulator` and `Schedulers` importable packages. Run commands from the repository root so imports such as `from NS_Simulator...` and `from Schedulers...` resolve correctly.

## Requirements

The project currently has no `requirements.txt` or `pyproject.toml`. Install the main dependencies into the same Python environment used to run the scripts:

```bash
python -m pip install numpy pandas matplotlib seaborn pulp
```

The optimization scheduler uses PuLP. The current comparison workflow is configured to use the HiGHS executable when it is installed:

```bash
brew install highs
```

On macOS with Homebrew, the current code expects HiGHS at:

```text
/opt/homebrew/bin/highs
```

If your executable is elsewhere, update the `path` argument in `Schedulers/OptimalSchedulling.py`.

Make sure `python` and `pip` refer to the same environment. For example:

```bash
python -c "import sys; print(sys.executable)"
python -m pip show pulp
```

If an environment variable called `PIP_PREFIX` redirects package installation to another Python installation, clear it before installing dependencies:

```bash
unset PIP_PREFIX
python -m pip install pulp
```

## Running the Main Comparison

The recommended entry point is:

```bash
python FINAL_ALL_SCHEDULER_COMPARISON.py
```

The script is configured in its module-level constants and lists. Before running, check at least:

- `carpets`: input folders under `Logs-Test/` to process.
- `DUTY_CYCLE`: documented mode value; the active loop in `main()` controls the actual run mode.
- `CONSIDER_OPTIMAL`: whether to run or load the optimization scheduler.
- `IMPORT_DATAANLAYSIS`: whether to load a previously saved analysis JSON.
- `MODEL`: path-loss model passed to `SimulatorCore`.
- `OUTPUT_IMAGES`: output directory for generated plots.

For a quick run, use one small input folder in `carpets`, for example:

```python
carpets = ["1_REPETITION_OKUMARA_RANDOM_FULL"]
```

To run only the heuristic schedulers, set:

```python
CONSIDER_OPTIMAL = False
```

To recompute the heuristic simulations and save a new analysis file, set:

```python
IMPORT_DATAANLAYSIS = False
```

The script may process many CSV files and create several plots, so a full comparison can take a long time.

## Simulation Flow

For each input CSV, `SimulatorCore` performs the following steps:

1. `TrafficGeneration` extracts device, gateway, and uplink tables.
2. End devices and gateways are registered with `NetworkServer`.
3. Uplink frames are grouped by sender and transmission time.
4. Confirmed uplinks are passed to the selected scheduler.
5. The scheduler chooses a gateway and RX1/RX2 downlink window, or reports a failure.
6. Channel/path-loss calculations determine whether the scheduled downlink reaches the end device.
7. `PacketLogger` records scheduling, delivery, collision, duty-cycle, and energy-related metrics.
8. `DataAnalysis` aggregates results and generates plots.

## Input Data

The simulator reads log files ending in `_uplinks.csv`. Files are expected to contain the tables used by `TrafficGeneration.py`, including:

- End-device table with columns such as `EndDeviceID`, `X`, `Y`, `Z`, and `SF`.
- Gateway table with either fixed gateway statistics or gateway locations `gatewayID`, `X`, `Y`, `Z`.
- Uplink table with columns such as `senderId`, `receiverID`, `sendTime`, `receivedTime`, `SF`, `SNR`, `RSSI`, `Ftype`, and frame-counter information.

The current parser expects the CSV log format produced by this project, including the header spacing used in columns such as ` sendTime` and ` receivedTime`.

Filenames are expected to contain parameters in this form:

```text
...period_<period>_gateway_<gateways>_seed_<seed>_percentage_<percentage>_log_N_ED_<devices>_log_uplinks.csv
```

These values are used to identify result rows and comparison scenarios.

## Scheduler Implementations

The comparison script currently exposes these scheduler families:

- `SchedulerBudgetGreedyEntropy_RSSI_v2`: resource-aware heuristic using RSSI, SNR, spreading factor, and duty-cycle information.
- `GreedyFuture`: heuristic with future-arrival information.
- `GreedyFuture_Rolling_Horizon_complete_v3`: rolling-horizon scheduler using `OptimalSchedulling_Portable` for local decisions.
- `DutyCyleControl`: duty-cycle-focused scheduler.
- `SchedulerTraditional`: traditional scheduling behavior.
- `TraditionalThreshold`: threshold-based traditional scheduler.
- `OptimalSchedulling`: global binary mixed-integer optimization model solved through PuLP.

All schedulers use the common base behavior in `NS_Simulator/Scheduler.py` and are passed into `SimulatorCore`.

## Optimization Scheduler

`Schedulers/OptimalSchedulling.py` creates a binary optimization model with RX1, RX2, and collision variables. It includes overlap, half-duplex, and duty-cycle constraints and maximizes scheduled downlinks.

The current solver configuration uses HiGHS with four threads and a 1% relative gap:

```python
pulp.HiGHS_CMD(
    path="/opt/homebrew/bin/highs",
    msg=1,
    gapRel=0.01,
    threads=4,
)
```

A relative gap allows the solver to stop after finding a solution sufficiently close to the best bound; it does not always prove exact optimality. Solver output includes:

```text
[LIP] solve started
[LIP] solve finished: ...
[LIP] status: ...
```

A missing `solve finished` line means the current optimization call is still running. A status of `Optimal` means the solver met its configured stopping criterion; `Feasible` means it found a valid schedule without proving optimality; `Not Solved` means no usable integer solution was confirmed before termination.

Optimization can be much slower for traces with dense overlapping arrivals because the model creates many binary variables and pairwise constraints. Cached files named `RESULTS_OPTIMAL_*.json` can be reused to avoid recomputing completed scenarios.

## Outputs

Depending on configuration, runs produce:

- `RESULTS_OPTIMAL_<folder>_<mode>.json`: cached optimization statistics.
- `dataAnalysis_<folder>_<mode>_<extra>.json`: serialized analysis tables and plotting metadata.
- Files and figures under `OUTPUT_IMAGES/`.
- Optional diagnostic CSV files when `SimulatorCore` is created with `Check_UL_GW=True`.
- Optional scheduler debug logs such as `debug_log_*.txt`.

Output paths are relative to the current working directory. Run from the repository root unless you intentionally configure absolute paths.

## Plotting and Reports

Plotting is implemented by the `DataAnalysis` class in `NS_Simulator/DataAnalysis.py`. Results are first stored with:

```python
dataAnalysis.add_data_outputTable(
    scheduler_name,
    scenario_parameters,
    statistics,
    color,
)
```

Scenario parameters normally use `(end_devices, gateways, percentage, period)`. The names accepted by the plotting functions are:

| Name | Tuple index | Meaning |
| --- | ---: | --- |
| `ed` | 0 | Number of end devices |
| `gw` | 1 | Number of gateways |
| `p` | 2 | Percentage of confirmed traffic |
| `pe` | 3 | Traffic period |

Use `dataAnalysis.sort_outputTable("gw,ed,p,pe")` to control the order in which scenarios appear. Sorting does not recalculate statistics.

### `plot_ack_percentages_by_param`

```python
dataAnalysis.plot_ack_percentages_by_param(
    split_param='p',
    metric='ACK%',
    limit=100,
    label='ACK%',
    scale=100.0,
    lm_inf=0.0,
)
```

Creates grouped bar charts comparing schedulers across scenarios. `split_param` selects the parameter used to create separate figures. Each bar is the mean metric value. Error bars show the minimum and maximum values stored for that scenario; they are not confidence intervals.

Examples:

```python
dataAnalysis.plot_ack_percentages_by_param('p', metric='ACK%', label='ACK (%)')
dataAnalysis.plot_ack_percentages_by_param('p', metric='CPSR', label='CPSR (%)')
dataAnalysis.plot_ack_percentages_by_param(
    'p',
    metric='Energy_Consumption_average_ed',
    limit=5.5,
    scale=1.0,
    lm_inf=2.5,
    label='Battery Duration (years)',
)
```

`scale` multiplies values before calculating the mean and error bars. Fractional metrics such as `ACK%` and `CPSR` normally use `100.0`; metrics already in their final units use `1.0`. `limit` and `lm_inf` define the y-axis range. Files use this pattern:

```text
<name_figures>_ack_percentages_by_param_<split_param>_<split_value>_<metric>.pdf
```

### `plot_ack_percentages_by_sf`

```python
dataAnalysis.plot_ack_percentages_by_sf(
    metric_prefix='ACK_sf',
    thres=100,
    title='',
    label='ACK%',
)
```

Creates one heatmap subplot per scheduler. Rows are SF7 through SF12, columns are scenarios, and cells contain the mean metric for each spreading factor. The function builds metric names by appending the SF number to `metric_prefix`; for example, `DL_PDR_sf` reads `DL_PDR_sf7` through `DL_PDR_sf12`.

Examples:

```python
dataAnalysis.plot_ack_percentages_by_sf('ACK_sf')
dataAnalysis.plot_ack_percentages_by_sf('DL_PDR_sf')
dataAnalysis.plot_ack_percentages_by_sf('USE_Rx1_sf')
dataAnalysis.plot_ack_percentages_by_sf('USE_Rx2_sf')
```

`thres` controls the upper color scale. The output is saved as:

```text
<name_figures>_ack_percentages_by_sf_<metric_prefix>.pdf
```

### `plot_ack_heatmap_by_param`

```python
dataAnalysis.plot_ack_heatmap_by_param(
    split_param='p',
    metric='ACK%',
    percentage=100,
    not_100=False,
    lm_inf=0,
)
```

Creates a heatmap for each value of `split_param`. Rows are schedulers, columns are scenarios, and cells contain the mean selected metric. The highest value in each scenario column is highlighted among the non-`Optimal` schedulers, which is useful for comparing heuristics.

Examples:

```python
dataAnalysis.plot_ack_heatmap_by_param('p', metric='ACK%')
dataAnalysis.plot_ack_heatmap_by_param('p', metric='CPSR')
dataAnalysis.plot_ack_heatmap_by_param(
    'p',
    metric='Energy_Consumption_average_ed',
    percentage=1,
    not_100=True,
)
```

Use `percentage=100` for fractional percentage metrics. Use `percentage=1` to preserve original units. With `not_100=True`, the color scale uses the largest observed value instead of being fixed at 100. Output files use:

```text
<name_figures>_ack_heatmap_by_param_<split_param>_<split_value>_<metric>.pdf
```

### `plot_ack_heatmap_by_param_separated`

```python
dataAnalysis.plot_ack_heatmap_by_param_separated(
    split_param='gw',
    metric='ACK%',
    percentage=100,
    not_100=False,
)
```

Creates a separate heatmap for each scheduler. The x-axis is the number of end devices, the y-axis is the number of gateways, and cells contain the mean metric for each combination. This is useful for examining how one scheduler scales with network size. The current implementation writes these figures to `Figures_holder/`.

### `plot_duty_cycle_consumption`

```python
dataAnalysis.plot_duty_cycle_consumption(
    title='Duty Cycle Consumption Over Time',
    split_param='gw',
    metric='ACK%',
)
```

Creates time-series subplots from `duty_cycle_monitoring`. RX1 and RX2 use separate y-axes because their reference limits differ. RX1 is shown against a 36-second limit and RX2 against a 360-second limit. Gateway traces are drawn as step plots over simulation time.

The `metric` argument is used in the filename; it does not select the duty-cycle data. Output files use:

```text
<name_figures>_duty_cycle_<scheduler>_<split_param>_<split_value>_<metric>.pdf
```

### `print_all_reports`

This is not a plot, but exports the values used by the plots to a CSV:

```python
dataAnalysis.print_all_reports(
    csv_dir='reports',
    filename='all_schedulers_report.csv',
)
```

The report contains the scheduler, scenario parameters, and the mean of every stored statistic. It is useful for custom plots and numerical analysis.

### Common metric names

The metric must match a key produced by `PacketLogger.compute_statistics()`. Common examples are:

- `ACK%`: acknowledgement or downlink success percentage.
- `CPSR`: confirmed-packet scheduling/reception ratio.
- `used_rx1_percentage_total`, `used_rx2_percentage_total`: total duty-cycle usage.
- `duty_cycle_Rx1_left`, `duty_cycle_Rx2_left`: remaining duty-cycle budget.
- `Loss_half_duplex%`: losses caused by gateway half-duplex conflicts.
- `Energy_Consumption_average_ed`: average energy consumption per end device.
- `Jains_index`: fairness measure.
- `DL_PDR_sf7` through `DL_PDR_sf12`: delivery ratio by spreading factor.
- `USE_Rx1_sf7` through `USE_Rx1_sf12`: RX1 usage by spreading factor.
- `USE_Rx2_sf7` through `USE_Rx2_sf12`: RX2 usage by spreading factor.

To discover the exact keys in a run, inspect `Simulator.logger.compute_statistics()` or export the table with `print_all_reports()`.

## Troubleshooting

### `ModuleNotFoundError` for project modules

Run the script from the repository root:

```bash
cd "/Users/carlosfernandez/Documents/PHD Carlos/Network-Server-Simulator"
python FINAL_ALL_SCHEDULER_COMPARISON.py
```

Use package imports for the current structure, for example:

```python
from NS_Simulator.NetworkServer import NetworkServer
from Schedulers.GreedyFuture import GreedyFuture
```

### `ModuleNotFoundError: No module named 'pulp'`

Install PuLP using the interpreter that runs the script:

```bash
python -m pip install pulp
```

If installation goes to the wrong Python environment, check and clear `PIP_PREFIX` as described above.

### Optimization appears stuck

Check whether the solver process is consuming CPU:

```bash
ps -axo pid,ppid,etime,%cpu,command | grep '[c]bc\|[h]ighs'
```

The optimizer may be working on a difficult MILP, especially for a dense trace. Run a smaller folder first, reuse cached result JSON files, or reduce the number of scenarios. Keep the laptop connected to power and use `caffeinate` for long runs:

```bash
caffeinate -dimsu python FINAL_ALL_SCHEDULER_COMPARISON.py
```

### Missing result or analysis directories

The comparison script creates missing directories before writing JSON output. If you add a new output path elsewhere, create its parent directory before opening the file.

## Notes

- Duty-cycle handling has separate `blocked` and `budget` modes in different scheduler implementations. Verify the active mode before comparing results.
- The optimizer and heuristic schedulers may use different prediction horizons and constraints, so compare their assumptions as well as their final metrics.
- Existing JSON caches can reflect older scheduler names or configurations. Regenerate them when changing scheduler definitions, input data, duty-cycle rules, or objective settings.
