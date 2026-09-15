"""Check that the map uses the original coordinates and independent layers."""
import csv
import json
import unittest

from csv_version.bus_map import DATA_DIR, build_map, load_map_points, map_payload


class BusMapTests(unittest.TestCase):
    def test_all_csv_points_are_mapped_without_moving_them(self):
        points = load_map_points()
        by_id = {p["id"]: p for p in points}
        expected_count = 0
        for filename, key in (("stops.csv", "stop_id"), ("pois.csv", "poi_id")):
            with (DATA_DIR / filename).open(encoding="utf-8-sig", newline="") as file:
                for row in csv.DictReader(file):
                    expected_count += 1
                    self.assertEqual(by_id[row[key]]["lat"], float(row["lat"]))
                    self.assertEqual(by_id[row[key]]["lon"], float(row["lon"]))
        self.assertEqual(len(points), expected_count)
        self.assertEqual(len(by_id), expected_count)

    def test_hiding_stops_keeps_every_store_and_removes_radius(self):
        points = load_map_points()
        data = map_payload(points, show_stops=False, show_radius=True)
        self.assertEqual(data["radius_centres"], [])
        self.assertEqual({p["id"] for p in data["points"]},
                         {p["id"] for p in points if p["kind"] == "便利商店"})

    def test_radius_is_in_meters_and_uses_only_stop_centres(self):
        data = map_payload(load_map_points(), show_radius=True, show_labels=False)
        self.assertFalse(data["show_labels"])
        self.assertEqual(data["radius_m"], 100)
        self.assertTrue(all(p["kind"] == "站牌" for p in data["radius_centres"]))

    def test_map_names_cannot_break_out_of_json_script(self):
        points = load_map_points()
        points[0]["name"] = '</script><script>alert(1)</script>'
        html = build_map(points)
        self.assertNotIn(points[0]["name"], html)
        payload = html.split('<script id="map-data" type="application/json">')[1].split('</script>')[0]
        self.assertEqual(json.loads(payload)["points"][0]["name"], points[0]["name"])


if __name__ == "__main__":
    unittest.main()
