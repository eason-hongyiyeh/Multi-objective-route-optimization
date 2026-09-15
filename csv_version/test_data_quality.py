"""Regression checks for missing travel times and the 100 m source selection."""
import json
import math
import tempfile
import unittest
from pathlib import Path

from csv_version import bus_queries as queries
from csv_version import generate_convenience_store_data as generator
from csv_version.estimate_bus_travel_times import motion_profile


class DataQualityTests(unittest.TestCase):
    def test_all_nearby_stores_are_kept_without_forcing_a_match(self):
        stops = [dict(stop_id="S1", lat="0", lon="0"),
                 dict(stop_id="S2", lat="1", lon="1")]
        elements = [dict(type="node", id=i, lat=0,
                         lon=math.degrees(distance / 6_371_000),
                         tags={"shop": "convenience", "name": f"Store {i}"})
                    for i, distance in enumerate((30, 99.9, 100.1), 1)]
        stores, _ = generator.select_stores(stops, {"response": {"elements": elements}})
        self.assertEqual(set(stores), {"node/1", "node/2"})
        self.assertTrue(all(link[0] == "S1" for s in stores.values() for link in s["links"]))

    def test_missing_bus_time_never_becomes_a_free_edge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generator.write_csv(root / "stops.csv", ["stop_id", "stop_name", "lat", "lon"],
                                [dict(stop_id=k, stop_name=k, lat=0, lon=0) for k in ("A", "B", "C")])
            generator.write_csv(root / "route_edges.csv",
                                ["edge_id", "route_name", "from_stop_id", "to_stop_id", "travel_time_min"],
                                [dict(edge_id="1", route_name="R", from_stop_id="A", to_stop_id="B", travel_time_min=0.375),
                                 dict(edge_id="2", route_name="R", from_stop_id="B", to_stop_id="C", travel_time_min="")])
            self.assertEqual(queries.find_bus_journey("A", "B", root).travel_time_min, 0.375)
            self.assertEqual(queries.find_direct_buses("A", "B", root)[0].travel_time_min, 0.375)
            self.assertIsNone(queries.find_bus_journey("A", "C", root))
            self.assertEqual(queries.find_direct_buses("A", "C", root), [])
            self.assertIsNone(queries.find_bus_journey("B", "A", root))

    def test_bad_snapping_does_not_produce_a_walking_time(self):
        reply = {"response": {"code": "Ok", "routes": [{"distance": 38, "duration": 30.3}],
                              "waypoints": [{"distance": 23.41}, {"distance": 15.25}]}}
        result = generator.walking_values(reply, 46.846)
        self.assertEqual(result["time_status"], "endpoint_needs_review")
        self.assertNotIn("walking_time_min", result)

    def test_saved_tables_have_valid_unique_relationships(self):
        read = lambda name: generator.read_csv(generator.DATA_DIR / (name + ".csv"))
        stops, pois, items = read("stops"), read("pois"), read("poi_items")
        stop_ids = {r["stop_id"] for r in stops}
        poi_ids = {r["poi_id"] for r in pois}
        item_ids = {r["item_id"] for r in items}
        self.assertEqual(len(poi_ids), len(pois))
        self.assertEqual([r["poi_id"] for r in pois], [f"P{i:03d}" for i in range(1, len(pois) + 1)])
        self.assertEqual(len({(r["osm_type"], r["osm_id"]) for r in pois}), len(pois))
        self.assertTrue(all(r["poi_type"] == "便利商店" for r in pois))
        links = read("stop_poi_mapping")
        self.assertEqual(len({(r["stop_id"], r["poi_id"]) for r in links}), len(links))
        for r in links:
            self.assertIn(r["stop_id"], stop_ids)
            self.assertIn(r["poi_id"], poi_ids)
            self.assertLessEqual(float(r["straight_distance_m"]), 100)
        for r in read("poi_item_mapping"):
            self.assertIn(r["poi_id"], poi_ids)
            self.assertIn(r["item_id"], item_ids)
        for r in read("route_edges"):
            self.assertIn(r["from_stop_id"], stop_ids)
            self.assertIn(r["to_stop_id"], stop_ids)
        coverage = read("stop_store_coverage")
        self.assertEqual({r["stop_id"] for r in coverage}, stop_ids)
        self.assertEqual(sum(int(r["store_count"]) for r in coverage), len(links))

    def test_saved_times_match_their_raw_evidence(self):
        cache = json.loads((generator.SOURCE_DIR / "walking_routes.json").read_text(encoding="utf-8"))
        for row in generator.read_csv(generator.DATA_DIR / "stop_poi_mapping.csv"):
            result = generator.walking_values(cache[row["source"]], float(row["straight_distance_m"]))
            self.assertEqual(row["time_status"], result["time_status"])
            self.assertEqual(row["walking_time_min"], str(result.get("walking_time_min", "")))

    def test_unknown_prices_and_ratings_remain_unknown(self):
        products = queries.find_product_pois("飯糰")
        self.assertTrue(products)
        self.assertTrue(all(p.price is None and p.rating is None and p.service_time_min is None for p in products))
        self.assertTrue(any(s.walking_time_min is None for p in products for s in p.nearby_stops))

    def test_short_segment_brakes_halfway_without_reaching_the_cap(self):
        result = motion_profile(100)
        self.assertEqual(result["travel_time_s"], 20)
        self.assertEqual(result["peak_speed_kmh"], 36)
        self.assertEqual(result["accel_distance_m"], 50)
        self.assertEqual(result["decel_distance_m"], 50)
        self.assertEqual(result["cruise_distance_m"], 0)

    def test_long_segment_includes_acceleration_and_braking(self):
        # 36 km/h = 10 m/s: 50 m accelerating, 300 m cruising, 50 m braking.
        result = motion_profile(400, speed_cap_kmh=36)
        self.assertEqual(result["travel_time_s"], 50)
        self.assertEqual(result["accel_time_s"], 10)
        self.assertEqual(result["cruise_time_s"], 30)
        self.assertEqual(result["decel_time_s"], 10)
        self.assertEqual(result["motion_profile"], "trapezoidal")

    def test_motion_boundary_and_invalid_inputs(self):
        self.assertEqual(motion_profile(100, speed_cap_kmh=36)["travel_time_s"], 20)
        self.assertEqual(motion_profile(0)["travel_time_s"], 0)
        for values in ((-1, 50, 1), (100, 0, 1), (100, 50, 0), (float("nan"), 50, 1)):
            with self.assertRaises(ValueError):
                motion_profile(*values)

    def test_each_saved_bus_edge_obeys_distance_speed_and_time_constraints(self):
        stops = {r["stop_id"]: r for r in generator.read_csv(generator.DATA_DIR / "stops.csv")}
        for row in generator.read_csv(generator.DATA_DIR / "route_edges.csv"):
            start, end = stops[row["from_stop_id"]], stops[row["to_stop_id"]]
            distance = generator.haversine_meters(float(start["lat"]), float(start["lon"]), float(end["lat"]), float(end["lon"]))
            a, v = float(row["acceleration_m_s2"]), float(row["peak_speed_kmh"]) / 3.6
            ta, tc, td = (float(row[k]) for k in ("accel_time_s", "cruise_time_s", "decel_time_s"))
            self.assertAlmostEqual(a * ta, v, places=5)
            self.assertAlmostEqual(float(row["deceleration_m_s2"]) * td, v, places=5)
            self.assertAlmostEqual(v * (ta / 2 + tc + td / 2), distance, places=4)
            self.assertAlmostEqual(float(row["travel_time_s"]), ta + tc + td, places=5)
            self.assertAlmostEqual(float(row["travel_time_min"]) * 60, ta + tc + td, places=4)
            self.assertLessEqual(v * 3.6, 50)
            self.assertGreater(float(row["travel_time_min"]), 0)
            self.assertEqual(row["time_status"], "kinematic_estimate")


if __name__ == "__main__":
    unittest.main()
