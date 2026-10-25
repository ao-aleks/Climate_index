# Poland ACI — local-data assessment

Grid: 4,092 unique rectangles across 16 voivodeships.
Period: 1961-01-01–2026-04-30; reference: 1961–1991 inclusive.
Water level excluded everywhere. No downloads attempted.

Complete daily period: 3,106/4,092 cells.
Complete reference period: 3,406/4,092 cells.
Valid national ACI months: 0/784.
Latest month (2026-04) valid cell ACI: 3,106/4,092.

A complete all-Poland ACI cannot be calculated from these local files.
The national result is missing rather than calculated from a changing subset.
All grid rectangles are mapped; grey rectangles have no supported value.

## Regions with incomplete daily coverage

                     rectangles  complete_reference  complete_weather_days_min  complete_weather_days_max  valid_aci_months_min  valid_aci_months_max  fully_complete_cells
region                                                                                                                                                                     
pomorskie                   253                 248                          0                      23861                     0                   784                   248
warminsko_mazurskie         329                 329                      12783                      23861                   420                   784                    29
wielkopolskie               401                   9                          0                      23861                     0                   784                     9
zachodniopomorskie          306                  17                          0                      23861                     0                   784                    17

Some additional points were recovered from the earlier Pomeranian rectangle archive; see the source audit.
Local hourly years were converted only when complete and when the corresponding daily year was absent.
Partial archives were ignored. Input files and previous notebooks were not modified.

Numerical formula checks: 23 comparisons passed, plus a missing-day mask check.

Open poland_aci_interactive_map.html in a browser for the offline map.