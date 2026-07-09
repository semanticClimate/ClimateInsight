/**
 * climate-wiki.js
 * ───────────────
 * Drop this script into any HTML page to get:
 *  • Hover tooltip  — first sentence from Wikipedia
 *  • Click modal    — full Wikipedia article in an iframe
 *
 * Usage:
 *   <script src="climate-wiki.js"></script>
 *
 * Works on the original ipcc_reference.html without modifying it —
 * just add this one <script> tag before </body>.
 */

(function () {
    "use strict";

    /* ── 1. TERM → WIKIPEDIA ARTICLE MAP ─────────────────────────────── */
    const WIKI_MAP = {
        "greenhouse gas emissions": "Greenhouse gas emissions",
        "greenhouse gases": "Greenhouse gas",
        "greenhouse gas": "Greenhouse gas",
        "carbon dioxide removal": "Carbon dioxide removal",
        "bioenergy with carbon capture and storage": "Bioenergy with carbon capture and storage",
        "atlantic meridional overturning circulation": "Atlantic meridional overturning circulation",
        "integrated assessment model": "Integrated assessment modelling",
        "ecosystem-based adaptation": "Ecosystem-based adaptation",
        "nationally determined contribution": "Nationally determined contribution",
        "equilibrium climate sensitivity": "Climate sensitivity",
        "transient climate response": "Climate sensitivity",
        "nature-based solutions": "Nature-based solutions",
        "climate-smart agriculture": "Climate-smart agriculture",
        "sustainable development": "Sustainable development",
        "climate change": "Climate change",
        "global warming": "Global warming",
        "global surface temperature": "Global surface temperature",
        "global mean temperature": "Global mean surface temperature",
        "sea level rise": "Sea level rise",
        "sea-level rise": "Sea level rise",
        "paris agreement": "Paris Agreement",
        "loss and damage": "Loss and damage (climate change)",
        "radiative forcing": "Radiative forcing",
        "carbon budget": "Carbon budget",
        "carbon pricing": "Carbon price",
        "carbon capture": "Carbon capture and storage",
        "carbon sequestration": "Carbon sequestration",
        "carbon footprint": "Carbon footprint",
        "carbon tax": "Carbon tax",
        "carbon offset": "Carbon offset",
        "carbon cycle": "Carbon cycle",
        "carbon sink": "Carbon sink",
        "net zero": "Net zero emissions",
        "net-zero": "Net zero emissions",
        "net negative": "Negative emissions",
        "just transition": "Just transition",
        "energy transition": "Energy transition",
        "energy efficiency": "Energy efficiency",
        "climate resilience": "Climate resilience",
        "adaptive capacity": "Adaptive capacity",
        "maladaptation": "Maladaptation",
        "tipping point": "Tipping points in the climate system",
        "tipping points": "Tipping points in the climate system",
        "climate risk": "Climate risk",
        "climate action": "Climate change mitigation",
        "climate finance": "Climate finance",
        "climate system": "Climate system",
        "climate model": "Climate model",
        "climate governance": "Climate governance",
        "climate justice": "Climate justice",
        "food security": "Food security",
        "energy security": "Energy security",
        "stranded assets": "Stranded asset",
        "green economy": "Green economy",
        "ocean acidification": "Ocean acidification",
        "ocean warming": "Ocean heat content",
        "permafrost": "Permafrost",
        "glacier retreat": "Retreat of glaciers since 1850",
        "ice sheet": "Ice sheet",
        "coral bleaching": "Coral bleaching",
        "biodiversity loss": "Biodiversity loss",
        "extreme weather": "Extreme weather",
        "tropical cyclone": "Tropical cyclone",
        "storm surge": "Storm surge",
        "compound events": "Compound event",
        "urban heat island": "Urban heat island",
        "early warning system": "Early warning system",
        "managed retreat": "Managed retreat",
        "afforestation": "Afforestation",
        "reforestation": "Reforestation",
        "deforestation": "Deforestation",
        "electrification": "Electrification",
        "decarbonization": "Low-carbon economy",
        "decarbonisation": "Low-carbon economy",
        "renewable energy": "Renewable energy",
        "solar energy": "Solar energy",
        "wind energy": "Wind power",
        "green hydrogen": "Green hydrogen",
        "emissions trading": "Emissions trading",
        "cap and trade": "Emissions trading",
        "carbon market": "Carbon emission trading",
        "warming level": "Global warming",
        "overshoot": "Overshoot (climate)",
        "attribution": "Attribution of recent climate change",
        "sensitivity": "Climate sensitivity",
        "feedback": "Climate change feedback",
        "forcing": "Radiative forcing",
        "aerosols": "Aerosol",
        "aerosol": "Aerosol",
        "albedo": "Albedo",
        "precipitation": "Precipitation",
        "drought": "Drought",
        "wildfire": "Wildfire",
        "flood": "Flood",
        "heatwave": "Heat wave",
        "heat wave": "Heat wave",
        "adaptation": "Climate change adaptation",
        "mitigation": "Climate change mitigation",
        "emissions": "Greenhouse gas emissions",
        "resilience": "Climate resilience",
        "vulnerability": "Vulnerability (climate change)",
        "likelihood": "Likelihood",
        "uncertainty": "Uncertainty quantification",
        "equity": "Climate justice",
        "ipcc": "Intergovernmental Panel on Climate Change",
        "unfccc": "United Nations Framework Convention on Climate Change",
        "beccs": "Bioenergy with carbon capture and storage",
        "cdr": "Carbon dioxide removal",
        "ssp": "Shared Socioeconomic Pathways",
        "rcp": "Representative Concentration Pathway",
        "iam": "Integrated assessment modelling",
        "cop": "United Nations Climate Change conference",
        "dac": "Direct air capture",
        "methane": "Methane",
        "bioenergy": "Bioenergy",
        "hydrogen": "Hydrogen",
        "glacier": "Glacier",
        // ── NEW TERMS TO ADD ─────────────────────────────────────────────

        // Acronyms & organisations
        "ndc": "Nationally determined contribution",
        "ndcs": "Nationally determined contribution",
        "unfccc": "United Nations Framework Convention on Climate Change",
        "kyoto protocol": "Kyoto Protocol",
        "kyoto": "Kyoto Protocol",
        "sdg": "Sustainable Development Goals",
        "sdgs": "Sustainable Development Goals",
        "sustainable development goals": "Sustainable Development Goals",
        "sids": "Small Island Developing States",
        "small island developing states": "Small Island Developing States",
        "least developed countries": "Least developed countries",
        "ldcs": "Least Developed Countries",
        "warsaw international mechanism": "Warsaw International Mechanism for Loss and Damage",
        "sendai framework": "Sendai Framework",
        "montreal protocol": "Montreal Protocol",
        "wim": "Warsaw International Mechanism for Loss and Damage",
        "afolu": "Agriculture, forestry and other land use",
        "co2-ffi": "Fossil fuel combustion",
        "co2-lulucf": "Land use, land-use change and forestry",
        "lulucf": "Land use, land-use change and forestry",
        "gwp": "Global warming potential",
        "gwp100": "Global warming potential",
        "f-gases": "Fluorinated gases",
        "fluorinated gases": "Fluorinated gases",
        "hfcs": "Hydrofluorocarbon",
        "pfcs": "Perfluorocarbon",
        "n2o": "Nitrous oxide",
        "nitrous oxide": "Nitrous oxide",
        "tropospheric ozone": "Tropospheric ozone",
        "stratospheric ozone": "Ozone layer",
        "ozone depletion": "Ozone depletion",
        "ch4": "Methane",

        // Climate science terms
        "emissions gap": "Emissions gap",
        "implementation gap": "Emissions gap",
        "carbon intensity": "Carbon intensity",
        "energy intensity": "Energy intensity",
        "hard limits": "Limits to adaptation",
        "soft limits": "Limits to adaptation",
        "adaptation limits": "Limits to adaptation",
        "transformational adaptation": "Climate change adaptation",
        "incremental adaptation": "Climate change adaptation",
        "adaptation gap": "Limits to adaptation",
        "slow-onset events": "Slow onset event",
        "compound flooding": "Compound event",
        "fire weather": "Wildfire",
        "marine heatwave": "Marine heatwave",
        "marine heatwaves": "Marine heatwave",
        "heavy precipitation": "Precipitation",
        "cold wave": "Cold wave",
        "cold waves": "Cold wave",
        "cryosphere": "Cryosphere",
        "biosphere": "Biosphere",
        "land degradation": "Land degradation",
        "desertification": "Desertification",
        "coastal wetlands": "Wetland",
        "peatlands": "Peat",
        "mangroves": "Mangrove",
        "agroforestry": "Agroforestry",
        "agroecological": "Agroecology",
        "soil organic carbon": "Soil carbon",
        "evapotranspiration": "Evapotranspiration",
        "water scarcity": "Water scarcity",
        "water security": "Water security",
        "vector-borne diseases": "Vector-borne disease",
        "zoonoses": "Zoonosis",
        "zoonosis": "Zoonosis",
        "displacement": "Climate refugee",
        "climate migration": "Climate refugee",
        "climate hazard": "Climate risk",
        "climate hazards": "Climate risk",
        "climate pledges": "Nationally determined contribution",
        "overshoot pathways": "Overshoot (climate)",

        // Energy & tech
        "photovoltaic": "Photovoltaics",
        "solar pv": "Photovoltaics",
        "pv": "Photovoltaics",
        "lithium-ion batteries": "Lithium-ion battery",
        "battery storage": "Battery storage",
        "electric vehicles": "Electric vehicle",
        "electric vehicle": "Electric vehicle",
        "evs": "Electric vehicle",
        "internal combustion engine": "Internal combustion engine",
        "levelised cost of energy": "Levelized cost of energy",
        "lcoe": "Levelized cost of energy",
        "fuel switching": "Fuel switching",
        "energy demand": "Energy demand",
        "demand side management": "Demand-side management",
        "direct air capture": "Direct air capture",
        "carbon removal": "Carbon dioxide removal",
        "co2 removals": "Carbon dioxide removal",

        // Policy & finance
        "green bonds": "Green bond",
        "green bond": "Green bond",
        "climate litigation": "Climate litigation",
        "carbon taxes": "Carbon tax",
        "concessional": "Concessional loan",
        "public-private partnerships": "Public–private partnership",
        "climate services": "Climate services",
        "anticipatory financing": "Anticipatory action",
        "disaster risk management": "Disaster risk reduction",
        "disaster risk reduction": "Disaster risk reduction",
        "climate literacy": "Climate literacy",
        "rights-based": "Rights-based approach",
        "just-transition": "Just transition",
        "social safety nets": "Social safety net",
        "social safety net": "Social safety net",
        "indigenous peoples": "Indigenous peoples",

        // Ecosystems
        "ecosystem services": "Ecosystem services",
        "biodiversity": "Biodiversity",
        "species loss": "Biodiversity loss",
        "habitat": "Habitat",
        "wetland": "Wetland",
        "wetlands": "Wetland",
        "coral reef": "Coral reef",
        "coral reefs": "Coral reef",
        "arctic sea ice": "Arctic sea ice",
        "snow cover": "Snow cover",
        "greenland ice sheet": "Greenland ice sheet",
        "land use change": "Land use, land-use change and forestry",
        "land-use change": "Land use, land-use change and forestry",
        "sustainable land management": "Sustainable land management",
        "urban green infrastructure": "Green infrastructure",
        "blue infrastructure": "Blue-green infrastructure",
        "urban greening": "Green infrastructure",
        // Climate variability & Earth system
        "el niño": "El Niño–Southern Oscillation",
        "el nino": "El Niño–Southern Oscillation",
        "la niña": "El Niño–Southern Oscillation",
        "la nina": "El Niño–Southern Oscillation",
        "enso": "El Niño–Southern Oscillation",
        "southern oscillation": "El Niño–Southern Oscillation",
        "enso-neutral": "El Niño–Southern Oscillation",
        "pacific decadal oscillation": "Pacific decadal oscillation",
        "pdo": "Pacific decadal oscillation",
        "atlantic multidecadal oscillation": "Atlantic Multidecadal Oscillation",
        "amo": "Atlantic Multidecadal Oscillation",
        "indian ocean dipole": "Indian Ocean Dipole",
        "iod": "Indian Ocean Dipole",
        "polar vortex": "Polar vortex",
        "jet stream": "Jet stream",
        "hadley cell": "Hadley cell",
        "walker circulation": "Walker circulation",
        "monsoon": "Monsoon",
        "asian monsoon": "Monsoon",
        "atmospheric river": "Atmospheric river",
        "blocking high": "Atmospheric blocking",
        "atmospheric blocking": "Atmospheric blocking",

        // Greenhouse gases & chemistry
        "co2": "Carbon dioxide",
        "carbon dioxide": "Carbon dioxide",
        "water vapour": "Water vapor",
        "water vapor": "Water vapor",
        "black carbon": "Black carbon",
        "organic carbon aerosol": "Organic carbon",
        "sulfate aerosol": "Sulfate aerosol",
        "methane hydrate": "Methane clathrate",
        "methane hydrates": "Methane clathrate",

        // Climate feedbacks
        "ice-albedo feedback": "Ice–albedo feedback",
        "water vapour feedback": "Water vapor feedback",
        "water vapor feedback": "Water vapor feedback",
        "cloud feedback": "Cloud feedback",
        "permafrost thaw": "Permafrost",
        "permafrost carbon": "Permafrost carbon feedback",
        "carbon-climate feedback": "Carbon cycle feedback",
        "carbon cycle feedback": "Carbon cycle feedback",

        // Oceans & cryosphere
        "thermohaline circulation": "Thermohaline circulation",
        "marine ice sheet instability": "Marine ice sheet instability",
        "marine ice cliff instability": "Marine ice cliff instability",
        "ice shelf": "Ice shelf",
        "sea ice": "Sea ice",
        "antarctic ice sheet": "Antarctic ice sheet",
        "west antarctic ice sheet": "West Antarctic Ice Sheet",
        "east antarctic ice sheet": "East Antarctic Ice Sheet",
        "glacial lake outburst flood": "Glacial lake outburst flood",
        "glof": "Glacial lake outburst flood",
        "ocean circulation": "Ocean circulation",
        "ocean deoxygenation": "Ocean deoxygenation",
        "ocean stratification": "Ocean stratification",

        // Hazards
        "flash drought": "Flash drought",
        "megadrought": "Megadrought",
        "dust storm": "Dust storm",
        "dust bowl": "Dust Bowl",
        "river flooding": "River flood",
        "coastal flooding": "Coastal flood",
        "flash flood": "Flash flood",
        "heat stress": "Heat stress",
        "humid heat": "Wet-bulb temperature",
        "wet bulb temperature": "Wet-bulb temperature",
        "wet-bulb temperature": "Wet-bulb temperature",
        "fire danger": "Wildfire",
        "fire regime": "Fire regime",

        // Mitigation & carbon
        "negative emissions technologies": "Negative emissions",
        "net-negative emissions": "Negative emissions",
        "residual emissions": "Residual emissions",
        "abatement": "Emission reduction",
        "emissions intensity": "Emissions intensity",
        "lifecycle emissions": "Life-cycle greenhouse gas emissions",
        "scope 1 emissions": "Scope 1 emissions",
        "scope 2 emissions": "Scope 2 emissions",
        "scope 3 emissions": "Scope 3 emissions",
        "embodied carbon": "Embodied carbon",
        "blue carbon": "Blue carbon",
        "soil carbon sequestration": "Soil carbon",
        "enhanced weathering": "Enhanced weathering",
        "biochar": "Biochar",
        "mineralization": "Carbon mineralization",

        // Energy transition
        "renewables": "Renewable energy",
        "grid flexibility": "Grid flexibility",
        "energy storage": "Energy storage",
        "smart grid": "Smart grid",
        "distributed energy": "Distributed generation",
        "microgrid": "Microgrid",
        "clean energy": "Clean energy",
        "low-carbon electricity": "Low-carbon energy",
        "zero-carbon energy": "Zero-carbon energy",

        // Socioeconomic scenarios
        "shared socioeconomic pathways": "Shared Socioeconomic Pathways",
        "representative concentration pathways": "Representative Concentration Pathway",
        "ssp1": "Shared Socioeconomic Pathways",
        "ssp2": "Shared Socioeconomic Pathways",
        "ssp3": "Shared Socioeconomic Pathways",
        "ssp4": "Shared Socioeconomic Pathways",
        "ssp5": "Shared Socioeconomic Pathways",
        "rcp2.6": "Representative Concentration Pathway",
        "rcp4.5": "Representative Concentration Pathway",
        "rcp6.0": "Representative Concentration Pathway",
        "rcp8.5": "Representative Concentration Pathway",

        // Adaptation & resilience
        "adaptive management": "Adaptive management",
        "transformative adaptation": "Climate change adaptation",
        "risk management": "Risk management",
        "climate-proofing": "Climate resilience",
        "disaster resilience": "Disaster resilience",
        "residual risk": "Residual risk",

        // Ecosystems
        "ecosystem restoration": "Ecosystem restoration",
        "rewilding": "Rewilding",
        "forest degradation": "Forest degradation",
        "primary forest": "Primary forest",
        "old-growth forest": "Old-growth forest",
        "kelp forest": "Kelp forest",
        "seagrass": "Seagrass",
        "salt marsh": "Salt marsh",

        // Human impacts
        "food systems": "Food system",
        "water resources": "Water resources",
        "human health": "Human health",
        "livelihoods": "Livelihood",
        "climate-sensitive diseases": "Climate-sensitive disease",
        "vector expansion": "Vector-borne disease",

        // IPCC terminology
        "very high confidence": "Confidence",
        "high confidence": "Confidence",
        "medium confidence": "Confidence",
        "low confidence": "Confidence",
        "very likely": "Likelihood",
        "likely": "Likelihood",
        "unlikely": "Likelihood",
        "virtually certain": "Likelihood",
        "extremely likely": "Likelihood",
        // Atmospheric science
        "boundary layer": "Atmospheric boundary layer",
        "planetary boundary layer": "Atmospheric boundary layer",
        "troposphere": "Troposphere",
        "stratosphere": "Stratosphere",
        "mesosphere": "Mesosphere",
        "thermosphere": "Thermosphere",
        "lapse rate": "Lapse rate",
        "environmental lapse rate": "Environmental lapse rate",
        "adiabatic lapse rate": "Adiabatic lapse rate",
        "inversion": "Temperature inversion",
        "temperature inversion": "Temperature inversion",
        "convection": "Atmospheric convection",
        "deep convection": "Atmospheric convection",
        "subsidence": "Atmospheric subsidence",
        "humidity": "Humidity",
        "relative humidity": "Relative humidity",
        "specific humidity": "Specific humidity",
        "dew point": "Dew point",
        "cloud condensation nuclei": "Cloud condensation nuclei",
        "ccn": "Cloud condensation nuclei",
        "cloud microphysics": "Cloud microphysics",
        "cirrus cloud": "Cirrus cloud",
        "cumulus cloud": "Cumulus cloud",
        "stratus cloud": "Stratus cloud",

        // Radiation
        "shortwave radiation": "Shortwave radiation",
        "longwave radiation": "Longwave radiation",
        "incoming solar radiation": "Solar irradiance",
        "solar irradiance": "Solar irradiance",
        "solar constant": "Solar constant",
        "infrared radiation": "Infrared radiation",
        "outgoing longwave radiation": "Outgoing longwave radiation",
        "earth's energy balance": "Earth's energy budget",
        "energy budget": "Earth's energy budget",

        // Ocean
        "mixed layer": "Ocean mixed layer",
        "mixed layer depth": "Mixed layer depth",
        "upwelling": "Upwelling",
        "downwelling": "Downwelling",
        "coastal upwelling": "Upwelling",
        "ocean currents": "Ocean circulation",
        "salinity": "Salinity",
        "ocean salinity": "Salinity",
        "thermocline": "Thermocline",
        "halocline": "Halocline",
        "pycnocline": "Pycnocline",
        "sea surface salinity": "Sea surface salinity",
        "sea surface height": "Sea surface height",
        "sea surface anomalies": "Sea surface height anomaly",

        // Ice & snow
        "snow albedo": "Snow albedo",
        "snowpack": "Snowpack",
        "snow melt": "Snowmelt",
        "snowmelt": "Snowmelt",
        "ice melt": "Ice melt",
        "ice loss": "Ice mass loss",
        "glacial mass balance": "Glacier mass balance",
        "mass balance": "Glacier mass balance",
        "ice core": "Ice core",
        "firn": "Firn",
        "ground ice": "Ground ice",

        // Carbon cycle
        "carbon stock": "Carbon stock",
        "carbon stocks": "Carbon stock",
        "carbon pool": "Carbon pool",
        "carbon pools": "Carbon pool",
        "carbon flux": "Carbon flux",
        "carbon source": "Carbon source",
        "terrestrial carbon": "Terrestrial carbon",
        "ocean carbon": "Ocean carbon",
        "blue carbon ecosystems": "Blue carbon",
        "forest carbon": "Forest carbon",
        "soil respiration": "Soil respiration",
        "net ecosystem exchange": "Net ecosystem exchange",
        "nee": "Net ecosystem exchange",
        "net ecosystem productivity": "Net ecosystem productivity",
        "nep": "Net ecosystem productivity",
        "net primary productivity": "Net primary productivity",
        "npp": "Net primary productivity",
        "gross primary productivity": "Gross primary productivity",
        "gpp": "Gross primary productivity",

        // Climate metrics
        "warming rate": "Rate of global warming",
        "temperature anomaly": "Temperature anomaly",
        "surface air temperature": "Surface air temperature",
        "global average temperature": "Global mean surface temperature",
        "climatology": "Climatology",
        "baseline period": "Climate reference period",
        "reference period": "Climate reference period",
        "historical baseline": "Climate reference period",
        "climate normal": "Climate normal",

        // Modelling
        "earth system model": "Earth system model",
        "esm": "Earth system model",
        "general circulation model": "General circulation model",
        "gcm": "General circulation model",
        "global climate model": "General circulation model",
        "regional climate model": "Regional climate model",
        "rcm": "Regional climate model",
        "ensemble": "Ensemble simulation",
        "ensemble mean": "Ensemble simulation",
        "hindcast": "Hindcast",
        "reanalysis": "Atmospheric reanalysis",
        "bias correction": "Bias correction",
        "parameterization": "Parameterization",
        "downscaling": "Climate downscaling",
        "statistical downscaling": "Climate downscaling",
        "dynamical downscaling": "Climate downscaling",

        // Extremes
        "return period": "Return period",
        "return level": "Return level",
        "1-in-100 year flood": "Return period",
        "100-year flood": "Return period",
        "extreme precipitation": "Extreme precipitation",
        "extreme rainfall": "Extreme precipitation",
        "extreme heat": "Heat wave",
        "cold extremes": "Cold wave",
        "record-breaking heat": "Heat wave",

        // Hydrology
        "runoff": "Runoff",
        "streamflow": "Streamflow",
        "river discharge": "River discharge",
        "watershed": "Watershed",
        "catchment": "Drainage basin",
        "drainage basin": "Drainage basin",
        "groundwater": "Groundwater",
        "aquifer": "Aquifer",
        "water table": "Water table",
        "surface water": "Surface water",
        "hydrological cycle": "Hydrological cycle",

        // Agriculture
        "crop yield": "Crop yield",
        "crop productivity": "Crop productivity",
        "irrigation": "Irrigation",
        "rainfed agriculture": "Rainfed agriculture",
        "precision agriculture": "Precision agriculture",
        "livestock": "Livestock",
        "pasture": "Pasture",
        "rangeland": "Rangeland",

        // Forestry
        "forest management": "Forest management",
        "forest restoration": "Forest restoration",
        "forest resilience": "Forest resilience",
        "forest cover": "Forest cover",
        "tree cover": "Tree cover",
        "canopy": "Forest canopy",

        // Economics
        "mitigation cost": "Mitigation cost",
        "social cost of carbon": "Social cost of carbon",
        "scc": "Social cost of carbon",
        "cost-benefit analysis": "Cost-benefit analysis",
        "discount rate": "Discount rate",
        "externality": "Externality",
        "co-benefits": "Co-benefits",
        "trade-offs": "Trade-offs",

        // Adaptation
        "adaptation pathway": "Adaptation pathway",
        "adaptation planning": "Adaptation planning",
        "adaptation options": "Adaptation options",
        "adaptive governance": "Adaptive governance",
        "community resilience": "Community resilience",
        "resilient infrastructure": "Climate-resilient infrastructure",

        // Risk
        "hazard": "Hazard",
        "exposure": "Exposure",
        "risk assessment": "Risk assessment",
        "risk reduction": "Risk reduction",
        "risk communication": "Risk communication",
        "multi-hazard": "Multi-hazard risk",
        "cascading risk": "Cascading risk",

        // Biodiversity
        "ecosystem function": "Ecosystem function",
        "ecosystem integrity": "Ecosystem integrity",
        "ecosystem degradation": "Ecosystem degradation",
        "species richness": "Species richness",
        "ecosystem connectivity": "Habitat connectivity",
        "habitat fragmentation": "Habitat fragmentation",
        "invasive species": "Invasive species",
        "keystone species": "Keystone species",
        "endemic species": "Endemic species",
        "pollinators": "Pollinator",

        // Coastal
        "coastal erosion": "Coastal erosion",
        "shoreline retreat": "Coastal erosion",
        "saltwater intrusion": "Saltwater intrusion",
        "sea wall": "Sea wall",
        "living shoreline": "Living shoreline",
        "coastal adaptation": "Coastal adaptation",

        // Health
        "heat mortality": "Heat-related mortality",
        "heat illness": "Heat-related illness",
        "air pollution": "Air pollution",
        "respiratory disease": "Respiratory disease",
        "malnutrition": "Malnutrition",
        "water-borne disease": "Water-borne disease",
        "vector expansion": "Disease vector expansion",

        // Renewable energy
        "hydropower": "Hydropower",
        "geothermal energy": "Geothermal energy",
        "tidal energy": "Tidal energy",
        "wave energy": "Wave energy",
        "offshore wind": "Offshore wind power",
        "onshore wind": "Onshore wind power",
        "floating solar": "Floating solar",
        "concentrated solar power": "Concentrated solar power",
        "csp": "Concentrated solar power",

        // Industry
        "industrial emissions": "Industrial greenhouse gas emissions",
        "cement emissions": "Cement industry emissions",
        "steel emissions": "Steel industry emissions",
        "aviation emissions": "Aviation emissions",
        "shipping emissions": "Shipping emissions",
        "hard-to-abate sectors": "Hard-to-abate sectors",

        // Transport
        "active transport": "Active transport",
        "public transit": "Public transport",
        "mode shift": "Transport mode shift",

        // Buildings
        "net zero building": "Net-zero energy building",
        "green building": "Green building",
        "passive house": "Passive house",
        "building retrofit": "Building retrofit",

        // Circular economy
        "circular economy": "Circular economy",
        "resource efficiency": "Resource efficiency",
        "material efficiency": "Material efficiency",
        "recycling": "Recycling",
        "reuse": "Reuse",
        "waste reduction": "Waste reduction",

        // Policy
        "adaptation fund": "Adaptation Fund",
        "green climate fund": "Green Climate Fund",
        "gcf": "Green Climate Fund",
        "global stocktake": "Global Stocktake",
        "gst": "Global Stocktake",
        "article 6": "Article 6 of the Paris Agreement",
        "article 6.2": "Article 6 of the Paris Agreement",
        "article 6.4": "Article 6 of the Paris Agreement",
        "long-term strategy": "Long-term low greenhouse gas emission development strategy",
        "lt-leds": "Long-term low greenhouse gas emission development strategy",

        // Observation
        "remote sensing": "Remote sensing",
        "satellite observations": "Satellite observations",
        "earth observation": "Earth observation",
        "weather station": "Meteorological station",
        "buoy": "Ocean buoy",
        "radiosonde": "Radiosonde",

        // Common IPCC wording
        "best estimate": "Best estimate",
        "confidence interval": "Confidence interval",
        "scenario": "Climate scenario",
        "pathway": "Climate pathway",
        "projection": "Climate projection",
        "observation": "Climate observation",
        "forcing agent": "Climate forcing",
        "detection": "Detection of climate change",
        "fingerprinting": "Climate change detection and attribution",
        "signal-to-noise ratio": "Signal-to-noise ratio",

        // Greenhouse gases
        "ghg": "Greenhouse gas",
        "ghgs": "Greenhouse gas",
        "greenhouse gas": "Greenhouse gas",
        "greenhouse gases": "Greenhouse gas",

        "co₂": "Carbon dioxide",
        "co2": "Carbon dioxide",
        "carbon dioxide": "Carbon dioxide",

        "ch₄": "Methane",
        "ch4": "Methane",
        "methane gas": "Methane",

        "n₂o": "Nitrous oxide",
        "nitrous oxide": "Nitrous oxide",

        "no": "Nitric oxide",
        "nitric oxide": "Nitric oxide",

        "no₂": "Nitrogen dioxide",
        "no2": "Nitrogen dioxide",
        "nitrogen dioxide": "Nitrogen dioxide",

        "nox": "Nitrogen oxides",
        "nitrogen oxides": "Nitrogen oxides",

        "so₂": "Sulfur dioxide",
        "so2": "Sulfur dioxide",
        "sulfur dioxide": "Sulfur dioxide",
        "sulphur dioxide": "Sulfur dioxide",

        "sox": "Sulfur oxides",
        "sulfur oxides": "Sulfur oxides",
        "sulphur oxides": "Sulfur oxides",

        "co": "Carbon monoxide",
        "carbon monoxide": "Carbon monoxide",

        "o₃": "Ozone",
        "ozone": "Ozone",

        "nh₃": "Ammonia",
        "nh3": "Ammonia",
        "ammonia": "Ammonia",

        "voc": "Volatile organic compound",
        "vocs": "Volatile organic compound",
        "volatile organic compounds": "Volatile organic compound",

        "nmvoc": "Non-methane volatile organic compound",
        "nmvocs": "Non-methane volatile organic compound",

        "halocarbons": "Halocarbon",
        "halocarbon": "Halocarbon",

        "cfc": "Chlorofluorocarbon",
        "cfcs": "Chlorofluorocarbon",
        "chlorofluorocarbons": "Chlorofluorocarbon",

        "hcfc": "Hydrochlorofluorocarbon",
        "hcfcs": "Hydrochlorofluorocarbon",
        "hydrochlorofluorocarbons": "Hydrochlorofluorocarbon",

        "hfc": "Hydrofluorocarbon",
        "hydrofluorocarbons": "Hydrofluorocarbon",

        "pfc": "Perfluorocarbon",
        "perfluorocarbons": "Perfluorocarbon",

        "sf6": "Sulfur hexafluoride",
        "sulfur hexafluoride": "Sulfur hexafluoride",

        "nf3": "Nitrogen trifluoride",
        "nitrogen trifluoride": "Nitrogen trifluoride",

        // Aerosols & particles
        "pm2.5": "PM2.5",
        "pm10": "PM10",
        "fine particulate matter": "PM2.5",
        "particulate matter": "Particulate matter",

        "brown carbon": "Brown carbon",
        "secondary organic aerosol": "Secondary organic aerosol",
        "primary aerosol": "Primary aerosol",
        "secondary aerosol": "Secondary aerosol",

        // Carbon accounting
        "co2 equivalent": "Carbon dioxide equivalent",
        "co₂ equivalent": "Carbon dioxide equivalent",
        "co2e": "Carbon dioxide equivalent",
        "co₂e": "Carbon dioxide equivalent",

        "ghg emissions": "Greenhouse gas emissions",
        "anthropogenic emissions": "Anthropogenic emissions",
        "biogenic emissions": "Biogenic emissions",
        "fugitive emissions": "Fugitive emissions",

        "gross emissions": "Gross greenhouse gas emissions",
        "net emissions": "Net greenhouse gas emissions",

        "annual emissions": "Annual greenhouse gas emissions",
        "historical emissions": "Historical greenhouse gas emissions",
        "cumulative emissions": "Cumulative carbon emissions",
        "consumption emissions": "Consumption-based emissions",
        "production emissions": "Production-based emissions",
        "territorial emissions": "Territorial emissions",

        // Carbon accounting scopes
        "scope 1": "Scope 1 emissions",
        "scope 2": "Scope 2 emissions",
        "scope 3": "Scope 3 emissions",

        // Climate metrics
        "gwp20": "Global warming potential",
        "gwp100": "Global warming potential",
        "global warming potential": "Global warming potential",

        "global temperature potential": "Global temperature potential",
        "gtp": "Global temperature potential",

        "radiative efficiency": "Radiative efficiency",
        "effective radiative forcing": "Effective radiative forcing",
        "erf": "Effective radiative forcing",

        // Emission sectors
        "power sector": "Electricity sector",
        "transport sector": "Transportation sector",
        "industrial sector": "Industry",
        "building sector": "Buildings",
        "residential sector": "Residential buildings",
        "commercial buildings": "Commercial buildings",

        // Land-use abbreviations
        "land use": "Land use",
        "land-use": "Land use",
        "land cover": "Land cover",
        "land cover change": "Land-cover change",

        // Climate targets
        "1.5°c": "1.5 °C global warming",
        "1.5 c": "1.5 °C global warming",
        "2°c": "2 °C global warming",
        "2 c": "2 °C global warming",

        // Atmospheric measurements
        "ppm": "Parts per million",
        "ppb": "Parts per billion",
        "ppt": "Parts per trillion",

        "mixing ratio": "Atmospheric mixing ratio",
        "atmospheric concentration": "Atmospheric concentration",

        // Fossil fuels
        "coal": "Coal",
        "oil": "Petroleum",
        "natural gas": "Natural gas",
        "fossil fuels": "Fossil fuel",
        "fossil fuel": "Fossil fuel",
        "fossil fuel combustion": "Fossil fuel combustion",

        // IPCC reporting
        "inventory": "Greenhouse gas inventory",
        "national inventory": "National greenhouse gas inventory",
        "emission inventory": "Greenhouse gas inventory",
        "inventory report": "National greenhouse gas inventory",

        // Atmospheric lifetime
        "atmospheric lifetime": "Atmospheric lifetime",
        "residence time": "Atmospheric lifetime",

        // Carbon capture
        "ccs": "Carbon capture and storage",
        "ccus": "Carbon capture, utilisation and storage",
        "ccu": "Carbon capture and utilisation",
        "carbon utilisation": "Carbon capture and utilisation",

        // Misc.
        "short-lived climate pollutants": "Short-lived climate pollutant",
        "slcp": "Short-lived climate pollutant",
        "slcps": "Short-lived climate pollutant",

        "long-lived greenhouse gases": "Long-lived greenhouse gas",
        "llghg": "Long-lived greenhouse gas",

        "air pollutant": "Air pollution",
        "criteria pollutants": "Criteria air pollutant",
        "UN": "United Nations"
    };

    /* ── 2. INJECT CSS ────────────────────────────────────────────────── */
    const CSS = `
    .cw-term {
      color: #1B4F9B;
      text-decoration: underline dotted #1B4F9B;
      cursor: pointer;
      border-radius: 2px;
      font-weight: bold;
      transition: background 0.15s;
    }
    .cw-term:hover {
      background: #e8f5ee;
      text-decoration: underline solid #1B4F9B;
    }

    /* Tooltip */
    #cw-tooltip {
      display: none;
      position: fixed;
      z-index: 99997;
      background: #fff;
      border: 1px solid #c8e6d5;
      border-left: 4px solid #1B4F9B;
      border-radius: 7px;
      padding: 10px 14px;
      max-width: 320px;
      font-size: 13px;
      line-height: 1.55;
      color: #1a1a1a;
      box-shadow: 0 4px 18px rgba(0,0,0,0.13);
      pointer-events: none;
      font-family: system-ui, sans-serif;
    }
    #cw-tooltip .cw-tt-title {
      font-weight: 700;
      font-size: 13.5px;
      color: #1B4F9B;
      margin-bottom: 5px;
    }
    #cw-tooltip .cw-tt-body {
      color: #333;
    }
    #cw-tooltip .cw-tt-loading {
      color: #999;
      font-style: italic;
    }
    #cw-tooltip .cw-tt-hint {
      margin-top: 7px;
      font-size: 11px;
      color: #888;
    }

    /* Modal overlay */
    #cw-overlay {
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(0,0,0,0.52);
      z-index: 99998;
      align-items: center;
      justify-content: center;
      font-family: system-ui, sans-serif;
    }
    #cw-overlay.cw-open { display: flex; }

    /* Modal box */
    #cw-modal {
      background: #fff;
      border-radius: 12px;
      width: min(1000px, 95vw);
      height: 96vh;
      max-height: 96vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 10px 50px rgba(0,0,0,0.28);
      overflow: hidden;
    }
    #cw-modal-header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 14px 18px;
      background: #1B4F9B;
      color: #fff;
      flex-shrink: 0;
    }
    #cw-modal-header svg {
      flex-shrink: 0;
      opacity: 0.85;
    }
    #cw-modal-title {
      flex: 1;
      margin: 0;
      font-size: 17px;
      font-weight: 600;
      letter-spacing: 0.01em;
    }
    #cw-modal-close {
      background: rgba(255,255,255,0.15);
      border: none;
      color: #fff;
      font-size: 18px;
      cursor: pointer;
      border-radius: 6px;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.15s;
    }
    #cw-modal-close:hover { background: rgba(255,255,255,0.28); }

    #cw-modal-iframe-wrap {
      flex: 1;
      overflow: hidden;
      position: relative;
    }
    #cw-modal-loading {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: #f9fafb;
      font-size: 14px;
      color: #888;
      gap: 10px;
    }
    #cw-modal-iframe {
      width: 100%;
      height: 100%;
      border: none;
      display: block;
    }

    #cw-modal-footer {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 9px 18px;
      border-top: 1px solid #eee;
      flex-shrink: 0;
      font-size: 12px;
      color: #999;
    }
    #cw-modal-footer a {
      color: #1B4F9B;
      text-decoration: none;
      font-weight: 500;
    }
    #cw-modal-footer a:hover { text-decoration: underline; }

    /* Loading spinner */
    @keyframes cw-spin { to { transform: rotate(360deg); } }
    .cw-spinner {
      width: 20px; height: 20px;
      border: 2px solid #ddd;
      border-top-color: #1B4F9B;
      border-radius: 50%;
      animation: cw-spin 0.7s linear infinite;
    }
  `;

    const styleEl = document.createElement("style");
    styleEl.textContent = CSS;
    document.head.appendChild(styleEl);


    /* ── 3. BUILD DOM ─────────────────────────────────────────────────── */

    // Tooltip
    const tooltip = document.createElement("div");
    tooltip.id = "cw-tooltip";
    tooltip.innerHTML = `
    <div class="cw-tt-title"></div>
    <div class="cw-tt-body cw-tt-loading">Loading…</div>
    <div class="cw-tt-hint">Click to open full article</div>
  `;
    document.body.appendChild(tooltip);

    // Modal
    const overlay = document.createElement("div");
    overlay.id = "cw-overlay";
    overlay.innerHTML = `
    <div id="cw-modal">
      <div id="cw-modal-header">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>
        </svg>
        <h2 id="cw-modal-title">Wikipedia</h2>
        <button id="cw-modal-close" title="Close (Esc)">✕</button>
      </div>
      <div id="cw-modal-iframe-wrap">
        <div id="cw-modal-loading">
          <div class="cw-spinner"></div> Loading Wikipedia…
        </div>
        <iframe id="cw-modal-iframe" src="" sandbox="allow-same-origin allow-scripts allow-popups allow-forms"></iframe>
      </div>
      <div id="cw-modal-footer">
        <span>Source: <strong>Wikipedia</strong></span>
        <a id="cw-modal-ext" href="#" target="_blank" rel="noopener">Open in Wikipedia ↗</a>
      </div>
    </div>
  `;
    document.body.appendChild(overlay);

    /* ── 4. MODAL LOGIC ───────────────────────────────────────────────── */
    const iframe = overlay.querySelector("#cw-modal-iframe");
    const loadingDiv = overlay.querySelector("#cw-modal-loading");

    function openModal(wikiTitle, displayText) {
        // If we are in the iframe, send message to parent window
        if (window !== window.parent) {
            window.parent.postMessage({ type: "OPEN_WIKI_MODAL", wikiTitle, displayText }, "*");
            return;
        }

        const mobileUrl = `https://en.m.wikipedia.org/wiki/${encodeURIComponent(wikiTitle)}`;
        const desktopUrl = `https://en.wikipedia.org/wiki/${encodeURIComponent(wikiTitle)}`;
        overlay.querySelector("#cw-modal-title").textContent = displayText;
        overlay.querySelector("#cw-modal-ext").href = desktopUrl;
        loadingDiv.style.display = "flex";
        iframe.src = "";
        iframe.onload = () => { loadingDiv.style.display = "none"; };
        iframe.src = mobileUrl;
        overlay.classList.add("cw-open");
    }

    // Listen for modal requests from child iframe
    window.addEventListener("message", (e) => {
        if (e.data && e.data.type === "OPEN_WIKI_MODAL") {
            openModal(e.data.wikiTitle, e.data.displayText);
        }
    });

    function closeModal() {
        overlay.classList.remove("cw-open");
        iframe.src = "";
        loadingDiv.style.display = "flex";
    }

    overlay.querySelector("#cw-modal-close").addEventListener("click", closeModal);
    overlay.addEventListener("click", (e) => { if (e.target === overlay) closeModal(); });
    
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

    /* ── 5. WIKIPEDIA SUMMARY API + CACHE ────────────────────────────── */
    const summaryCache = {};

    function fetchSummary(wikiTitle, cb) {
        if (summaryCache[wikiTitle]) { cb(summaryCache[wikiTitle]); return; }
        fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(wikiTitle)}`)
            .then((r) => r.json())
            .then((d) => {
                const plain = d.extract || "";
                const first = plain.split(/(?<=[.!?])\s+/)[0] || plain || "No definition found.";
                summaryCache[wikiTitle] = first;
                cb(first);
            })
            .catch(() => {
                summaryCache[wikiTitle] = "Could not load definition.";
                cb(summaryCache[wikiTitle]);
            });
    }

    /* ── 6. TOOLTIP POSITIONING ──────────────────────────────────────── */
    function positionTooltip(e) {
        const pad = 12;
        const tw = tooltip.offsetWidth || 320;
        const th = tooltip.offsetHeight || 80;

        let minX = pad;
        let maxX = window.innerWidth - pad;
        let minY = pad;
        let maxY = window.innerHeight - pad;

        try {
            const panel = window.parent.document.querySelector('.source-panel');
            if (panel && window.frameElement) {
                const panelRect = panel.getBoundingClientRect();
                const iframeRect = window.frameElement.getBoundingClientRect();

                // Convert panel bounds to iframe's coordinate system
                const limitLeft = panelRect.left - iframeRect.left;
                const limitRight = panelRect.right - iframeRect.left;
                const limitTop = panelRect.top - iframeRect.top;
                const limitBottom = panelRect.bottom - iframeRect.top;

                // Ensure boundaries are constrained within the iframe's visible viewport
                minX = Math.max(0, limitLeft) + pad;
                maxX = Math.min(window.innerWidth, limitRight) - pad;
                minY = Math.max(0, limitTop) + pad;
                maxY = Math.min(window.innerHeight, limitBottom) - pad;
            }
        } catch (err) {
            // Fallback to window dimensions if cross-origin blocked or missing
        }

        // Try placing to the right of the cursor
        let x = e.clientX + 16;
        if (x + tw > maxX) {
            x = e.clientX - tw - 8;
        }

        // Try placing below the cursor
        let y = e.clientY + 16;
        if (y + th > maxY) {
            y = e.clientY - th - 8;
        }

        // Final clamp to ensure the tooltip is entirely within bounds
        if (x < minX) x = minX;
        if (x + tw > maxX) x = maxX - tw;
        if (y < minY) y = minY;
        if (y + th > maxY) y = maxY - th;

        tooltip.style.left = x + "px";
        tooltip.style.top = y + "px";
    }

    /* ── 7. TEXT NODE WALKER + TERM INJECTION ────────────────────────── */
    // Sort terms longest-first to prevent partial matches
    const sortedTerms = Object.keys(WIKI_MAP).sort((a, b) => b.length - a.length);
    const pattern = new RegExp(
        "\\b(" + sortedTerms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|") + ")\\b",
        "gi"
    );

    // Tags we skip entirely (don't touch their text content)
    const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA", "CODE", "PRE", "A", "BUTTON", "INPUT", "SELECT"]);

    function wrapTermsInNode(textNode) {
        const text = textNode.nodeValue;
        if (!pattern.test(text)) return;       // fast exit
        pattern.lastIndex = 0;

        const frag = document.createDocumentFragment();
        let last = 0, m;
        pattern.lastIndex = 0;

        while ((m = pattern.exec(text)) !== null) {
            if (m.index > last) {
                frag.appendChild(document.createTextNode(text.slice(last, m.index)));
            }
            const matched = m[0];
            const key = matched.toLowerCase();
            const wikiTitle = WIKI_MAP[key];
            if (!wikiTitle) {
                frag.appendChild(document.createTextNode(matched));
            } else {
                const a = document.createElement("a");
                a.className = "cw-term";
                a.href = "#";
                a.textContent = matched;
                a.dataset.wiki = wikiTitle;
                a.dataset.display = matched;

                a.addEventListener("mouseenter", (e) => {
                    tooltip.querySelector(".cw-tt-title").textContent = matched;
                    tooltip.querySelector(".cw-tt-body").textContent = "Loading…";
                    tooltip.querySelector(".cw-tt-body").className = "cw-tt-body cw-tt-loading";
                    tooltip.style.display = "block";
                    positionTooltip(e);
                    fetchSummary(wikiTitle, (text) => {
                        tooltip.querySelector(".cw-tt-body").textContent = text;
                        tooltip.querySelector(".cw-tt-body").className = "cw-tt-body";
                    });
                });
                a.addEventListener("mousemove", positionTooltip);
                a.addEventListener("mouseleave", () => { tooltip.style.display = "none"; });
                a.addEventListener("click", (e) => {
                    e.preventDefault();
                    tooltip.style.display = "none";
                    openModal(wikiTitle, matched);
                });

                frag.appendChild(a);
            }
            last = m.index + m[0].length;
        }

        if (last < text.length) {
            frag.appendChild(document.createTextNode(text.slice(last)));
        }

        textNode.parentNode.replaceChild(frag, textNode);
    }

    function walkNode(node) {
        if (node.nodeType === Node.TEXT_NODE) {
            wrapTermsInNode(node);
            return;
        }
        if (node.nodeType !== Node.ELEMENT_NODE) return;
        if (SKIP_TAGS.has(node.tagName)) return;
        if (node.classList && node.classList.contains("cw-term")) return;

        // Collect children first (walking live NodeList while modifying it is unsafe)
        const children = Array.from(node.childNodes);
        children.forEach(walkNode);
    }

    /* ── 8. RUN ───────────────────────────────────────────────────────── */
    function run() {
        // Only scan and highlight terms if we are inside the IPCC iframe
        if (window !== window.parent) {
            walkNode(document.body);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", run);
    } else {
        run();
    }
})();
