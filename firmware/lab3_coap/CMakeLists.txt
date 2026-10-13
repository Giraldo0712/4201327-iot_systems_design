cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(lab3_coap)

target_sources(app PRIVATE src/main.c src/env_temp.c src/valve.c)

# Collect the CoAP resources of the "soilsense" service into one list
zephyr_linker_sources(DATA_SECTIONS sections-ram.ld)
zephyr_iterable_section(NAME coap_resource_soilsense GROUP DATA_REGION ${XIP_ALIGN_WITH_INPUT})
