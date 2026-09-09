-- 1. 查看每條公車路線包含多少段路徑
SELECT route_name, COUNT(*) AS edge_count, SUM(travel_time_min) AS total_minutes
FROM route_edges
GROUP BY route_name
ORDER BY route_name;

-- 2. 查詢站牌附近的地點
SELECT
    s.stop_name,
    p.poi_name,
    p.poi_type,
    sp.walking_time_min
FROM stop_poi_mapping AS sp
JOIN stops AS s ON s.stop_id = sp.stop_id
JOIN pois AS p ON p.poi_id = sp.poi_id
ORDER BY s.stop_name, sp.walking_time_min;

-- 3. 查詢地點販售的品項和價格
SELECT
    p.poi_name,
    i.item_name,
    pim.price,
    pim.service_time_min
FROM poi_item_mapping AS pim
JOIN pois AS p ON p.poi_id = pim.poi_id
JOIN poi_items AS i ON i.item_id = pim.item_id
ORDER BY p.poi_name, i.item_name;
