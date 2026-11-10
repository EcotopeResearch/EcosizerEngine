# Volumetric heat capacity of water [BTU / (gallon · °F)]
_RHO_CP: float = 8.353535

# Unit conversion: 1 W = 3.412142 BTU/hr  (equivalently, 1 kW = 3.412142 kBTU/hr)
_BTUH_PER_W: float = 3.412142

# Default Nominal COPs
_ELECTRIC_RESISTANCE_COP = 0.95
_GAS_COP = 0.95 # ER equivellant
_HEAT_PUMP_COP = 2.5

# Nominal COP by water heater heating type (used by NominalPerformanceMap)
_NOMINAL_COP_BY_HEATING_TYPE: dict[str, float] = {
    "electric_resistance": _ELECTRIC_RESISTANCE_COP,
    "gas":                 _GAS_COP,
    "heat_pump":           _HEAT_PUMP_COP,
}
_HEATING_TYPES: tuple[str, ...] = tuple(_NOMINAL_COP_BY_HEATING_TYPE)
