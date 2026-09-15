"""Estimate stop-to-stop motion from rest to rest; these are not observed bus times."""
import argparse
import math
from datetime import datetime, timezone

try:
    from .generate_convenience_store_data import DATA_DIR, read_csv, write_csv, haversine_meters
except ImportError:  # Direct execution from the project root.
    from generate_convenience_store_data import DATA_DIR, read_csv, write_csv, haversine_meters


def motion_profile(distance_m, speed_cap_kmh=50.0, acceleration_m_s2=1.0):
    """Symmetric constant acceleration/braking, with optional constant-speed cruising."""
    if not all(math.isfinite(v) for v in (distance_m, speed_cap_kmh, acceleration_m_s2)):
        raise ValueError("Inputs must be finite")
    if distance_m < 0 or speed_cap_kmh <= 0 or acceleration_m_s2 <= 0:
        raise ValueError("Distance must be nonnegative; speed and acceleration must be positive")
    cap = speed_cap_kmh / 3.6
    a = acceleration_m_s2
    peak = min(cap, math.sqrt(a * distance_m))
    accel_distance = peak * peak / (2 * a)
    cruise_distance = max(0.0, distance_m - 2 * accel_distance)
    accel_time = peak / a
    cruise_time = cruise_distance / cap
    total_time = 2 * accel_time + cruise_time
    return dict(model_distance_m=distance_m, speed_cap_kmh=speed_cap_kmh,
                acceleration_m_s2=a, deceleration_m_s2=a, peak_speed_kmh=peak * 3.6,
                accel_distance_m=accel_distance, cruise_distance_m=cruise_distance,
                decel_distance_m=accel_distance, accel_time_s=accel_time,
                cruise_time_s=cruise_time, decel_time_s=accel_time,
                travel_time_s=total_time, travel_time_min=total_time / 60,
                motion_profile="trapezoidal" if distance_m > cap * cap / a else "triangular")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speed-cap-kmh", type=float, default=50.0)
    parser.add_argument("--acceleration-m-s2", type=float, default=1.0)
    args = parser.parse_args()
    # Validate even for an empty dataset, before any writes.
    motion_profile(0, args.speed_cap_kmh, args.acceleration_m_s2)
    stops = {r["stop_id"]: r for r in read_csv(DATA_DIR / "stops.csv")}
    rows = read_csv(DATA_DIR / "route_edges.csv")
    computed_at = datetime.now(timezone.utc).isoformat()
    for row in rows:
        start, end = stops[row["from_stop_id"]], stops[row["to_stop_id"]]
        distance = haversine_meters(float(start["lat"]), float(start["lon"]),
                                    float(end["lat"]), float(end["lon"]))
        model = motion_profile(distance, args.speed_cap_kmh, args.acceleration_m_s2)
        row.update({k: round(v, 6) if isinstance(v, float) else v for k, v in model.items()})
        row.update(time_status="kinematic_estimate", distance_method="haversine_straight_line",
                   source="stops.csv; csv_version/estimate_bus_travel_times.py",
                   model_version="symmetric_rest_to_rest_v1", computed_at=computed_at)
    if rows:
        write_csv(DATA_DIR / "route_edges.csv", list(rows[0]), rows)
    print(f"Updated {len(rows)} edges: speed cap {args.speed_cap_kmh} km/h, acceleration/braking {args.acceleration_m_s2} m/s^2.")
    print("Distance: existing stop coordinates, Haversine straight line. No dwell, signals, traffic, or road geometry.")


if __name__ == "__main__":
    main()
