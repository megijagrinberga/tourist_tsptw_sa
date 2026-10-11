# TSP with Time Windows (Simulated Annealing)

Practical assignment for the course "Praktiskā kombinatoriālā optimizācija".

A tourist starts at the hotel, visits all sights and returns to the hotel. Each sight has opening hours: if the tourist arrives early they wait, and a sight cannot be visited after it closes. The goal is to find the visiting order with the shortest total duration. The problem is solved with **Simulated Annealing (SA)**, written from scratch, and compared with an exact solver on small instances.

## How to run

Only Python 3 is needed, no extra libraries.

```bash
python tourist.py
```

The script generates 27 test instances (n = 8 to 100 sights, 3 random seeds each), runs SA 5 times per instance, runs the exact solver for n <= 15, prints the results and saves them to `results.csv`. It takes several minutes.

## Files

* `tourist.py` - the whole implementation (problem, SA, exact solver, testing).
* `param_test.py` - a small sensitivity test for the SA parameters (cooling rate 0.90 / 0.95 / 0.98 and lateness penalty 1 / 10 / 100) on three mid-size instances. It only prints a table and does not change the main results. Run it with `python param_test.py` (needs `tourist.py` in the same folder).
* `instances.json` - the generated test instances.
* `results.csv` - the results. Separator is `;` and decimal mark is `,` so it opens correctly in Excel with Latvian settings.

## Result columns

All durations are in minutes.

* `instance`, `n` - instance name and number of sights.
* `sa_best`, `sa_mean` - best and average tour duration over the 5 SA runs.
* `feasible_rate` - share of SA runs that found a valid route (1.0 = all 5).
* `sa_time_avg` - average SA run time in seconds.
* `optimum`, `exact_time` - optimal duration and exact solver time in seconds. Filled only for n <= 15 (empty if the exact solver was not run or timed out).
* `gap_opt_best_percent`, `gap_opt_mean_percent` - how much worse the best / average SA result is than the optimum, in percent (n <= 15 only).
* `lower_bound` - a value that no route can beat: the latest opening time plus the visit time and the trip back to the hotel.
* `gap_lb_best_percent`, `gap_lb_mean_percent` - how far the best / average SA result is from the lower bound, in percent. The true optimum lies between the lower bound and SA's result.
* `hidden_route` - duration of the random route used to build the time windows, which is a valid but unoptimised route.
