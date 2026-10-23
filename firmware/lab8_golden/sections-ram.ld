#include <zephyr/linker/iterable_sections.h>

/* RAM list that COAP_RESOURCE_DEFINE(..., soilsense, ...) entries are collected into */
ITERABLE_SECTION_RAM(coap_resource_soilsense, Z_LINK_ITERABLE_SUBALIGN)
