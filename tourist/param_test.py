import statistics
import tourist

# small sensitivity test: vary one SA parameter at a time on a few mid-size instances
INSTANCES = [(20, 2), (30, 2), (50, 1)]
CONFIGS = [  # (cooling rate, lateness penalty)
    (0.90, 10.0), (0.95, 10.0), (0.98, 10.0),
    (0.95, 1.0), (0.95, 100.0),
]

for n, seed in INSTANCES:
    problem = tourist.generate_problem(n, seed)
    lb = tourist.lower_bound(problem)
    print(f"\n{problem.name}  (lower bound {lb:.1f})")
    print("cooling  penalty  feasible  best     mean     gap_lb_mean%  time_s")
    for cooling, penalty in CONFIGS:
        tourist.COOLING_RATE = cooling
        tourist.LATENESS_PENALTY = penalty
        runs = [tourist.simulated_annealing(problem, s) for s in range(tourist.SA_RUNS)]
        durations = [d for route, d, sec in runs if route is not None]
        seconds = statistics.mean(sec for route, d, sec in runs)
        if durations:
            mean = statistics.mean(durations)
            print(f"{cooling:<8} {penalty:<8} {len(durations)}/{tourist.SA_RUNS}     "
                  f"{min(durations):<8.1f} {mean:<8.1f} {(mean - lb) / lb * 100:<13.2f} {seconds:.2f}")
        else:
            print(f"{cooling:<8} {penalty:<8} 0/{tourist.SA_RUNS}     no valid route found")
