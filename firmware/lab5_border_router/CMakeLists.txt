cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(lab5_border_router)

# omr_guard.c, rcp_tx_security.c and forward_nd.c work around Zephyr and
# ESP32-C6 RCP bugs without patching the Zephyr tree; each file says which.
target_sources(app PRIVATE src/main.c src/omr_guard.c src/rcp_tx_security.c src/forward_nd.c)
target_link_options(app PUBLIC
  -Wl,--wrap=get_ot_slaac_address
  -Wl,--wrap=otPlatRadioGetCaps
  -Wl,--wrap=net_route_ipv6_packet
)
