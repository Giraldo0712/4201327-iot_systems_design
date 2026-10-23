cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(lab7_telemetry)

target_sources(app PRIVATE src/main.c src/reading.c src/env_temp.c src/valve.c src/coaps_client.c
			   src/health.c src/dtls_stats.c)
# dtls_stats.c counts failed handshakes by wrapping the Mbed TLS call
target_link_options(app PUBLIC -Wl,--wrap=mbedtls_ssl_handshake)

# Collect the CoAP resources of the "soilsense" service into one list
zephyr_linker_sources(DATA_SECTIONS sections-ram.ld)
zephyr_iterable_section(NAME coap_resource_soilsense GROUP DATA_REGION ${XIP_ALIGN_WITH_INPUT})
