import streamlit as st

from bus_queries import (
    find_best_shopping_trip,
    find_bus_journey,
    find_direct_buses,
    find_places,
    find_product_pois,
    get_route_stop_sequence,
    list_all_stops,
    list_routes,
)


def render_bus_journey(journey, heading: str) -> None:
    st.markdown(f"**{heading}**")
    st.caption(
        f"轉乘 {journey.transfer_count} 次｜乘車約 "
        f"{journey.travel_time_min} 分鐘｜共 {journey.stop_count} 站"
    )
    for index, leg in enumerate(journey.legs, start=1):
        st.write(
            f"{index}. 搭乘 {leg.route_name}："
            f"{leg.start_stop.stop_name} → {leg.end_stop.stop_name}"
            f"（{leg.stop_count} 站，約 {leg.travel_time_min} 分鐘）"
        )
        st.caption(" → ".join(stop.stop_name for stop in leg.stops))
        if index < len(journey.legs):
            st.info(f"在「{leg.end_stop.stop_name}」轉乘。")


st.set_page_config(page_title="公車站牌查詢", layout="wide")
st.title("公車資料查詢")

tab_complete, tab_stops, tab_route, tab_direct, tab_product = st.tabs(
    ["完整行程", "所有站牌", "路線站序", "公車路徑", "商品搜尋"]
)

with tab_complete:
    stops = list_all_stops()
    complete_stop_options = [f"{stop.stop_id} {stop.stop_name}" for stop in stops]
    complete_stop_id_by_option = {
        option: option.split(" ", 1)[0] for option in complete_stop_options
    }

    col_start, col_place, col_end = st.columns(3)
    with col_start:
        complete_start_option = st.selectbox(
            "完整行程起點",
            complete_stop_options,
            index=0,
        )
    with col_place:
        place_query = st.text_input(
            "要去的地點或購買商品",
            placeholder="例如：三民市場、博物館、蘋果、玩具",
        )
    with col_end:
        complete_end_option = st.selectbox(
            "完整行程終點",
            complete_stop_options,
            index=min(1, len(complete_stop_options) - 1),
        )

    complete_start_id = complete_stop_id_by_option[complete_start_option]
    complete_end_id = complete_stop_id_by_option[complete_end_option]
    basic_journey = find_bus_journey(complete_start_id, complete_end_id)
    selected_visit = None
    selected_visit_label = ""

    if place_query:
        visit_options = {}
        for product in find_product_pois(place_query):
            label = (
                f"購買「{product.item_name}」｜{product.poi_name}｜"
                f"{product.price} 元"
            )
            visit_options[label] = product
        for place in find_places(place_query):
            label = f"前往地點｜{place.poi_name}｜{place.poi_type}"
            visit_options.setdefault(label, place)

        if visit_options:
            selected_visit_label = st.selectbox(
                "選擇途中要前往的地點",
                list(visit_options),
            )
            selected_visit = visit_options[selected_visit_label]
        else:
            st.warning(
                f"找不到「{place_query}」的販售地點或 POI，"
                "以下仍提供起點到終點的公車路線。"
            )

    complete_trip = (
        find_best_shopping_trip(
            complete_start_id,
            complete_end_id,
            selected_visit,
        )
        if selected_visit
        else None
    )

    if complete_trip:
        visit_stop = complete_trip.shopping_stop
        st.subheader(
            f"{complete_start_option.split(' ', 1)[1]} → "
            f"{selected_visit.poi_name} → "
            f"{complete_end_option.split(' ', 1)[1]}"
        )
        st.caption(
            f"{selected_visit_label}｜鄰近站：{visit_stop.stop_name}｜"
            f"步行約 {visit_stop.walking_time_min} 分鐘｜公車轉乘合計 "
            f"{complete_trip.total_transfer_count} 次｜全程約 "
            f"{complete_trip.total_time_min} 分鐘"
        )

        if complete_trip.starts_at_shopping_stop:
            st.success(f"起點就是地點鄰近站「{visit_stop.stop_name}」。")
        else:
            render_bus_journey(
                complete_trip.inbound_journey,
                "第一段：起點 → 地點鄰近站",
            )
        st.info(
            f"在「{visit_stop.stop_name}」下車，步行約 "
            f"{visit_stop.walking_time_min} 分鐘到 "
            f"{selected_visit.poi_name}；完成後返回同一站牌繼續搭車。"
        )
        if complete_trip.ends_at_shopping_stop:
            st.success(f"地點鄰近站「{visit_stop.stop_name}」就是最終終點。")
        else:
            render_bus_journey(
                complete_trip.outbound_journey,
                "第二段：地點鄰近站 → 終點",
            )
    else:
        if selected_visit:
            st.warning(
                f"目前無法安排經過「{selected_visit.poi_name}」的完整路線，"
                "以下改為提供起點到終點的公車路線。"
            )
        if complete_start_id == complete_end_id:
            st.info("起點與終點相同，不需要搭乘公車。")
        elif basic_journey:
            st.subheader(
                f"{complete_start_option.split(' ', 1)[1]} → "
                f"{complete_end_option.split(' ', 1)[1]}"
            )
            render_bus_journey(basic_journey, "起點 → 終點")
        else:
            st.error("目前的公車資料中沒有可到達終點的路徑。")

with tab_stops:
    stops = list_all_stops()
    st.caption(f"共 {len(stops)} 個站牌")
    st.dataframe(
        [
            {
                "站牌編號": stop.stop_id,
                "站牌名稱": stop.stop_name,
                "緯度": stop.lat,
                "經度": stop.lon,
            }
            for stop in stops
        ],
        width="stretch",
        hide_index=True,
    )

with tab_route:
    routes = list_routes()
    selected_route = st.selectbox("選擇公車路線", routes)
    route_stops = get_route_stop_sequence(selected_route)

    st.caption(f"{selected_route} 共 {len(route_stops)} 個站牌")
    st.dataframe(
        [
            {
                "站序": stop.sequence,
                "站牌編號": stop.stop_id,
                "站牌名稱": stop.stop_name,
            }
            for stop in route_stops
        ],
        width="stretch",
        hide_index=True,
    )

with tab_direct:
    stops = list_all_stops()
    stop_options = [f"{stop.stop_id} {stop.stop_name}" for stop in stops]
    stop_id_by_option = {option: option.split(" ", 1)[0] for option in stop_options}

    col_start, col_end = st.columns(2)
    with col_start:
        start_option = st.selectbox("起點站", stop_options, index=0)
    with col_end:
        end_option = st.selectbox("終點站", stop_options, index=min(1, len(stop_options) - 1))

    start_stop_id = stop_id_by_option[start_option]
    end_stop_id = stop_id_by_option[end_option]
    direct_buses = find_direct_buses(start_stop_id, end_stop_id)

    if start_stop_id == end_stop_id:
        st.warning("起點和終點不能相同。")
    elif not direct_buses:
        journey = find_bus_journey(start_stop_id, end_stop_id)
        if journey is None:
            st.info("目前沒有查到可到達的公車路徑。")
        else:
            st.warning(
                f"沒有直達公車，以下方案需轉乘 {journey.transfer_count} 次，"
                f"乘車約 {journey.travel_time_min} 分鐘，共 {journey.stop_count} 站。"
            )
            for index, leg in enumerate(journey.legs, start=1):
                st.subheader(f"第 {index} 段：搭乘 {leg.route_name}")
                st.write(
                    f"從「{leg.start_stop.stop_name}」上車，"
                    f"到「{leg.end_stop.stop_name}」下車"
                    f"（{leg.stop_count} 站，約 {leg.travel_time_min} 分鐘）"
                )
                st.caption(" → ".join(stop.stop_name for stop in leg.stops))
                if index < len(journey.legs):
                    st.info(f"在「{leg.end_stop.stop_name}」轉乘下一班公車。")
    else:
        st.caption(f"查到 {len(direct_buses)} 條直達公車")
        st.dataframe(
            [
                {
                    "路線": bus.route_name,
                    "起點站序": bus.start_sequence,
                    "終點站序": bus.end_sequence,
                    "經過站數": bus.stop_count,
                    "預估時間": bus.travel_time_min,
                    "行經站牌": " -> ".join(stop.stop_name for stop in bus.stops),
                }
                for bus in direct_buses
            ],
            width="stretch",
            hide_index=True,
        )

with tab_product:
    stops = list_all_stops()
    shopping_stop_options = [f"{stop.stop_id} {stop.stop_name}" for stop in stops]
    shopping_stop_id_by_option = {
        option: option.split(" ", 1)[0] for option in shopping_stop_options
    }

    col_origin, col_destination, col_product = st.columns(3)
    with col_origin:
        shopping_start_option = st.selectbox(
            "採買起點站",
            shopping_stop_options,
            index=0,
        )
    with col_destination:
        shopping_end_option = st.selectbox(
            "採買後終點站",
            shopping_stop_options,
            index=min(1, len(shopping_stop_options) - 1),
        )
    with col_product:
        product_query = st.text_input(
            "輸入商品或服務名稱",
            placeholder="例如：熟食、夜市小吃、校園參訪",
        )

    if product_query:
        product_pois = find_product_pois(product_query)
        if not product_pois:
            st.info("目前沒有找到可購買此商品或服務的 POI。")
        else:
            st.caption(f"找到 {len(product_pois)} 筆結果")
            st.dataframe(
                [
                    {
                        "商品或服務": result.item_name,
                        "POI": result.poi_name,
                        "類型": result.poi_type,
                        "評分": result.rating,
                        "參考價格": result.price,
                        "預估停留時間": result.service_time_min,
                        "鄰近站牌": "、".join(
                            f"{stop.stop_name}（步行 {stop.walking_time_min} 分鐘）"
                            for stop in result.nearby_stops
                        )
                        or "尚無站牌資料",
                    }
                    for result in product_pois
                ],
                width="stretch",
                hide_index=True,
            )

            shopping_start_stop_id = shopping_stop_id_by_option[shopping_start_option]
            shopping_end_stop_id = shopping_stop_id_by_option[shopping_end_option]
            st.subheader("起點 → 採買站 → 終點")
            for result in product_pois:
                trip = find_best_shopping_trip(
                    shopping_start_stop_id,
                    shopping_end_stop_id,
                    result,
                )
                with st.expander(f"{result.poi_name}｜{result.item_name}", expanded=True):
                    if trip is None:
                        st.info("目前沒有可完成起點、採買站與終點的公車路徑。")
                        continue

                    shopping_stop = trip.shopping_stop
                    st.caption(
                        f"採買站：{shopping_stop.stop_name}｜步行到 POI 約 "
                        f"{shopping_stop.walking_time_min} 分鐘｜全程約 "
                        f"{trip.total_time_min} 分鐘"
                    )

                    st.markdown("**去程：起點 → 採買站**")
                    if trip.starts_at_shopping_stop:
                        st.success(
                            f"起點就是採買站「{shopping_stop.stop_name}」，"
                            f"步行約 {shopping_stop.walking_time_min} 分鐘可抵達 "
                            f"{result.poi_name}。"
                        )
                    else:
                        inbound = trip.inbound_journey
                        st.caption(
                            f"轉乘 {inbound.transfer_count} 次｜乘車約 "
                            f"{inbound.travel_time_min} 分鐘"
                        )
                        for index, leg in enumerate(inbound.legs, start=1):
                            st.write(
                                f"第 {index} 段：搭乘 {leg.route_name}，"
                                f"從「{leg.start_stop.stop_name}」到"
                                f"「{leg.end_stop.stop_name}」"
                            )
                            st.caption(" → ".join(stop.stop_name for stop in leg.stops))

                    st.markdown("**回程：採買站 → 終點**")
                    if trip.ends_at_shopping_stop:
                        st.success(f"採買站「{shopping_stop.stop_name}」就是終點。")
                    else:
                        outbound = trip.outbound_journey
                        st.caption(
                            f"轉乘 {outbound.transfer_count} 次｜乘車約 "
                            f"{outbound.travel_time_min} 分鐘"
                        )
                        for index, leg in enumerate(outbound.legs, start=1):
                            st.write(
                                f"第 {index} 段：搭乘 {leg.route_name}，"
                                f"從「{leg.start_stop.stop_name}」到"
                                f"「{leg.end_stop.stop_name}」"
                            )
                            st.caption(" → ".join(stop.stop_name for stop in leg.stops))
