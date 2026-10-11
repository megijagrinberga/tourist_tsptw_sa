import csv
import json
import math
import random
import statistics
import time

# penalty per minute of lateness (arriving after a sight has closed)
LATENESS_PENALTY = 10.0

# simulated annealing (SA) parameters
COOLING_RATE = 0.95
MOVES_PER_SIGHT = 20
MIN_TEMPERATURE = 0.05
START_ACCEPTANCE = 0.8
SA_RUNS = 5

# the exact solver is only used on small instances, it is too slow for larger ones
EXACT_MAX_SIGHTS = 15
EXACT_TIME_LIMIT = 60

# test instance sizes (number of sights) and random seeds
SIZES = [8, 10, 12, 15, 20, 30, 50, 75, 100]
SEEDS = [1, 2, 3]
MAP_SIZE = 30.0
WINDOW_SLACK = (120, 480)


class Problem:
    # point 0 is the hotel, points 1..n are the sights
    def __init__(self, name, coords, open_time, close_time, visit_time, hidden_route_duration=None):
        self.name = name
        self.coords = coords
        self.open_time = open_time
        self.close_time = close_time
        self.visit_time = visit_time
        self.hidden_route_duration = hidden_route_duration
        self.num_sights = len(coords) - 1
        self.travel_time = [[math.dist(a, b) for b in coords] for a in coords]

    def to_dict(self):
        return {"name": self.name, "coords": self.coords, "open_time": self.open_time,
                "close_time": self.close_time, "visit_time": self.visit_time,
                "hidden_route_duration": self.hidden_route_duration}


def generate_problem(num_sights, seed):
    rng = random.Random(seed)
    coords = [(MAP_SIZE / 2, MAP_SIZE / 2)]
    coords += [(rng.uniform(0, MAP_SIZE), rng.uniform(0, MAP_SIZE)) for _ in range(num_sights)]
    visit_time = [0] + [rng.randint(30, 60) for _ in range(num_sights)]
    open_time = [0] * (num_sights + 1)
    close_time = [0] * (num_sights + 1)
    problem = Problem(f"n{num_sights}_s{seed}", coords, open_time, close_time, visit_time)

    # make up a random "hidden" route and build the time windows around its arrival times,
    # so every instance is guaranteed to have at least one valid route
    hidden_route = list(range(1, num_sights + 1))
    rng.shuffle(hidden_route)
    time_now, position = 0.0, 0
    for sight in hidden_route:
        time_now += problem.travel_time[position][sight]
        arrival = time_now
        open_time[sight] = round(max(0, arrival - rng.randint(*WINDOW_SLACK)), 1)
        start = max(arrival, open_time[sight])
        close_time[sight] = round(start + rng.randint(*WINDOW_SLACK), 1)
        time_now = start + visit_time[sight]
        position = sight
    time_now += problem.travel_time[position][0]
    problem.hidden_route_duration = round(time_now, 1)
    return problem


def evaluate(problem, route):
    # returns: day duration, total lateness and the objective (duration + penalty)
    time_now, position, lateness = 0.0, 0, 0.0
    for sight in route:
        time_now += problem.travel_time[position][sight]
        if time_now < problem.open_time[sight]:
            time_now = problem.open_time[sight]
        if time_now > problem.close_time[sight]:
            lateness += time_now - problem.close_time[sight]
        time_now += problem.visit_time[sight]
        position = sight
    duration = time_now + problem.travel_time[position][0]
    return duration, lateness, duration + LATENESS_PENALTY * lateness


def lower_bound(problem):
    # no route can finish before the latest-opening sight has opened, been visited,
    # and the tourist has travelled back to the hotel (direct trip is the fastest possible)
    return max(problem.open_time[i] + problem.visit_time[i] + problem.travel_time[i][0]
               for i in range(1, problem.num_sights + 1))


def initial_route(problem):
    # start with the sights sorted by closing time (the earlier a sight closes, the earlier it is visited)
    return sorted(range(1, problem.num_sights + 1), key=lambda sight: problem.close_time[sight])


def random_neighbour(route, rng):
    # randomly pick one of three moves: swap, insert (move one sight) or reverse a segment
    neighbour = route[:]
    i, j = sorted(rng.sample(range(len(neighbour)), 2))
    move = rng.random()
    if move < 0.33:
        neighbour[i], neighbour[j] = neighbour[j], neighbour[i]
    elif move < 0.66:
        neighbour.insert(j, neighbour.pop(i))
    else:
        neighbour[i:j + 1] = reversed(neighbour[i:j + 1])
    return neighbour


def start_temperature(problem, route, rng):
    # choose the start temperature so that an average worsening is accepted with ~80% probability at first
    base_cost = evaluate(problem, route)[2]
    changes = [abs(evaluate(problem, random_neighbour(route, rng))[2] - base_cost) for _ in range(200)]
    average_change = sum(changes) / len(changes) or 1.0
    return -average_change / math.log(START_ACCEPTANCE)


def simulated_annealing(problem, seed):
    # returns the best valid route found, its duration and the run time (route = None if no valid route was found)
    rng = random.Random(seed)
    clock_start = time.time()

    current = initial_route(problem)
    duration, lateness, current_cost = evaluate(problem, current)
    best_route, best_duration = (current, duration) if lateness == 0 else (None, None)

    temperature = start_temperature(problem, current, rng)
    moves_per_temperature = max(50, MOVES_PER_SIGHT * problem.num_sights)
    while temperature > MIN_TEMPERATURE:
        for _ in range(moves_per_temperature):
            candidate = random_neighbour(current, rng)
            duration, lateness, cost = evaluate(problem, candidate)
            change = cost - current_cost
            # always accept a better solution; accept a worse one with a probability that drops as the temperature drops
            if change <= 0 or rng.random() < math.exp(-change / temperature):
                current, current_cost = candidate, cost
                if lateness == 0 and (best_route is None or duration < best_duration):
                    best_route, best_duration = candidate, duration
        temperature *= COOLING_RATE
    return best_route, best_duration, time.time() - clock_start


def solve_exactly(problem):
    # depth-first search with pruning - pruning never loses the optimum
    # returns the optimal duration, or None if the time limit ran out
    n = problem.num_sights
    best_duration = float("inf")
    timed_out = False
    deadline = time.time() + EXACT_TIME_LIMIT
    visited = set()

    def search(time_now, position, remaining_visit_time):
        nonlocal best_duration, timed_out
        if time.time() > deadline:
            timed_out = True
            return
        if len(visited) == n:
            best_duration = min(best_duration, time_now + problem.travel_time[position][0])
            return
        # prune the branch if even in the best case it cannot beat the best solution so far
        if time_now + remaining_visit_time + problem.travel_time[position][0] >= best_duration:
            return
        # prune the branch if some unvisited sight can no longer be reached before it closes
        for sight in range(1, n + 1):
            if sight not in visited and time_now + problem.travel_time[position][sight] > problem.close_time[sight]:
                return
        for sight in range(1, n + 1):
            if sight in visited:
                continue
            start = max(time_now + problem.travel_time[position][sight], problem.open_time[sight])
            if start > problem.close_time[sight]:
                continue
            visited.add(sight)
            search(start + problem.visit_time[sight], sight, remaining_visit_time - problem.visit_time[sight])
            visited.remove(sight)

    search(0.0, 0, sum(problem.visit_time))
    if timed_out or best_duration == float("inf"):
        return None
    return best_duration


def percent_gap(value, reference):
    return round((value - reference) / reference * 100, 2)


def test_problem(problem):
    # SA is random, so run it several times with different seeds
    runs = [simulated_annealing(problem, seed) for seed in range(SA_RUNS)]
    durations = [duration for route, duration, seconds in runs if route is not None]
    sa_seconds = statistics.mean(seconds for route, duration, seconds in runs)
    sa_best = min(durations) if durations else None
    sa_mean = statistics.mean(durations) if durations else None

    exact_duration, exact_seconds = None, None
    if problem.num_sights <= EXACT_MAX_SIGHTS:
        clock_start = time.time()
        exact_duration = solve_exactly(problem)
        exact_seconds = time.time() - clock_start

    lb = lower_bound(problem)

    return {
        "instance": problem.name,
        "n": problem.num_sights,
        "sa_best": round(sa_best, 2) if durations else "",
        "sa_mean": round(sa_mean, 2) if durations else "",
        "feasible_rate": len(durations) / SA_RUNS,
        "sa_time_avg": round(sa_seconds, 3),
        # exact optimum and gaps to it (only for small instances where the exact solver finished)
        "optimum": round(exact_duration, 2) if exact_duration is not None else "",
        "exact_time": round(exact_seconds, 3) if exact_duration is not None else "",
        "gap_opt_best_percent": percent_gap(sa_best, exact_duration) if durations and exact_duration is not None else "",
        "gap_opt_mean_percent": percent_gap(sa_mean, exact_duration) if durations and exact_duration is not None else "",
        # lower bound and gaps to it (for all instances; the real optimum is somewhere between)
        "lower_bound": round(lb, 2),
        "gap_lb_best_percent": percent_gap(sa_best, lb) if durations else "",
        "gap_lb_mean_percent": percent_gap(sa_mean, lb) if durations else "",
        # duration of the hidden route that was used to build the time windows (a valid but unoptimised route)
        "hidden_route": problem.hidden_route_duration,
    }


def save_results(rows, path="results.csv"):
    # semicolon separator and decimal comma so Excel with Latvian settings opens it in separate columns
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(rows[0].keys())
        for row in rows:
            writer.writerow([str(value).replace(".", ",") for value in row.values()])


def save_instances(problems, path="instances.json"):
    # human-readable JSON: one key per line, one point per line, other lists on a single line
    blocks = []
    for problem in problems:
        data = problem.to_dict()
        lines = [f'    "name": {json.dumps(data["name"])},']
        points = ",\n".join(f"      {json.dumps(point)}" for point in data["coords"])
        lines.append(f'    "coords": [\n{points}\n    ],')
        for key in ("open_time", "close_time", "visit_time"):
            lines.append(f'    "{key}": {json.dumps(data[key])},')
        lines.append(f'    "hidden_route_duration": {json.dumps(data["hidden_route_duration"])}')
        blocks.append("  {\n" + "\n".join(lines) + "\n  }")
    with open(path, "w", encoding="utf-8") as f:
        f.write("[\n" + ",\n".join(blocks) + "\n]\n")


def main():
    problems = [generate_problem(n, seed) for n in SIZES for seed in SEEDS]
    save_instances(problems)

    rows = []
    for problem in problems:
        row = test_problem(problem)
        rows.append(row)
        print(row, flush=True)
    save_results(rows)


if __name__ == "__main__":
    main()
