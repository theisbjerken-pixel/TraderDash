"""Stock universes for TraderDash.

Hierarchy, built by inclusion:

    Free < Nordic < International

Free, Nordic and International are assembled at the bottom of this file.
Edit the named lists. Do not edit the assembled universes by hand.

There is no login or payment. access.py decides which of these lists a plan may use.

Tickers are Yahoo Finance symbols. Nordic index lists follow published
constituents as of autumn 2026 and should be reviewed when the indices change.
The 20-name country lists are a selected set for review, not an index.
"""

from __future__ import annotations

TIERS = ("free", "nordic", "international")

TIER_LABELS = {
    "free": "Free",
    "nordic": "Nordic",
    "international": "International",
}


# --- Free: 10 Denmark, 10 Sweden, 10 Norway ---

FREE_DENMARK = {
    "NOVO-B.CO": "Novo Nordisk",
    "DSV.CO": "DSV",
    "DANSKE.CO": "Danske Bank",
    "MAERSK-B.CO": "Mærsk B",
    "VWS.CO": "Vestas",
    "GMAB.CO": "Genmab",
    "CARL-B.CO": "Carlsberg",
    "ORSTED.CO": "Ørsted",
    "COLO-B.CO": "Coloplast",
    "PNDORA.CO": "Pandora",
}

FREE_SWEDEN = {
    "VOLV-B.ST": "Volvo",
    "ATCO-A.ST": "Atlas Copco",
    "INVE-B.ST": "Investor",
    "AZN.ST": "AstraZeneca",
    "ERIC-B.ST": "Ericsson",
    "HM-B.ST": "H&M",
    "SEB-A.ST": "SEB",
    "SAND.ST": "Sandvik",
    "ABB.ST": "ABB",
    "SWED-A.ST": "Swedbank",
}

FREE_NORWAY = {
    "EQNR.OL": "Equinor",
    "DNB.OL": "DNB",
    "MOWI.OL": "Mowi",
    "NHY.OL": "Norsk Hydro",
    "TEL.OL": "Telenor",
    "KOG.OL": "Kongsberg Gruppen",
    "AKRBP.OL": "Aker BP",
    "ORK.OL": "Orkla",
    "YAR.OL": "Yara",
    "STB.OL": "Storebrand",
}


# --- Nordic large-cap indices ---
# Denmark: OMXC25, Nasdaq list as of August 2026.

OMXC25 = {
    "NOVO-B.CO": "Novo Nordisk",
    "NDA-DK.CO": "Nordea",
    "MAERSK-B.CO": "Mærsk B",
    "MAERSK-A.CO": "Mærsk A",
    "DSV.CO": "DSV",
    "DANSKE.CO": "Danske Bank",
    "GMAB.CO": "Genmab",
    "NSIS-B.CO": "Novonesis",
    "VWS.CO": "Vestas",
    "ORSTED.CO": "Ørsted",
    "COLO-B.CO": "Coloplast",
    "TRYG.CO": "Tryg",
    "DEMANT.CO": "Demant",
    "PNDORA.CO": "Pandora",
    "ALSYDB.CO": "AL Sydbank",
    "JYSK.CO": "Jyske Bank",
    "ISS.CO": "ISS",
    "ROCK-B.CO": "Rockwool",
    "FLS.CO": "FLSmidth",
    "AMBU-B.CO": "Ambu",
    "RBREW.CO": "Royal Unibrew",
    "GN.CO": "GN Store Nord",
    "ZEAL.CO": "Zealand Pharma",
    "NKT.CO": "NKT",
    "CARL-B.CO": "Carlsberg",
}

# Sweden: OMX Stockholm 30, Nasdaq list as of August 2026.

OMXS30 = {
    "ABB.ST": "ABB",
    "ADDT-B.ST": "Addtech",
    "ALFA.ST": "Alfa Laval",
    "ASSA-B.ST": "Assa Abloy",
    "AZN.ST": "AstraZeneca",
    "ATCO-A.ST": "Atlas Copco",
    "BOL.ST": "Boliden",
    "EPI-A.ST": "Epiroc",
    "EQT.ST": "EQT",
    "ERIC-B.ST": "Ericsson",
    "ESSITY-B.ST": "Essity",
    "EVO.ST": "Evolution",
    "HM-B.ST": "H&M",
    "HEXA-B.ST": "Hexagon",
    "INDU-C.ST": "Industrivärden",
    "INVE-B.ST": "Investor",
    "LIFCO-B.ST": "Lifco",
    "NIBE-B.ST": "Nibe",
    "NDA-SE.ST": "Nordea",
    "SAAB-B.ST": "Saab",
    "SAND.ST": "Sandvik",
    "SCA-B.ST": "SCA",
    "SEB-A.ST": "SEB",
    "SKA-B.ST": "Skanska",
    "SKF-B.ST": "SKF",
    "SHB-A.ST": "Handelsbanken",
    "SWED-A.ST": "Swedbank",
    "TEL2-B.ST": "Tele2",
    "TELIA.ST": "Telia",
    "VOLV-B.ST": "Volvo",
}

# Norway: OBX, Euronext composition extract of 30 September 2026.
# That public extract listed 23 names and was truncated. Bluenord was
# added in the September 2026 review. Add any missing constituent here.

OBX = {
    "EQNR.OL": "Equinor",
    "DNB.OL": "DNB",
    "KOG.OL": "Kongsberg Gruppen",
    "AKRBP.OL": "Aker BP",
    "NHY.OL": "Norsk Hydro",
    "MOWI.OL": "Mowi",
    "STB.OL": "Storebrand",
    "TEL.OL": "Telenor",
    "SUBC.OL": "Subsea 7",
    "YAR.OL": "Yara",
    "ORK.OL": "Orkla",
    "GJF.OL": "Gjensidige",
    "VAR.OL": "Vår Energi",
    "FRO.OL": "Frontline",
    "SALM.OL": "SalMar",
    "VEND.OL": "Vend Marketplaces",
    "NOD.OL": "Nordic Semiconductor",
    "AKER.OL": "Aker",
    "KMAR.OL": "Kongsberg Maritime",
    "TGS.OL": "TGS",
    "BWLPG.OL": "BW LPG",
    "HAUTO.OL": "Höegh Autoliners",
    "TOM.OL": "Tomra",
    "BLUEN.OL": "Bluenord",
}


# --- International: about 20 leading names per country ---
# Denmark, Sweden and Norway overlap the Nordic indices. United States,
# United Kingdom, Germany and France are the names International adds.

LEADING_DENMARK = {
    "NOVO-B.CO": "Novo Nordisk",
    "DSV.CO": "DSV",
    "DANSKE.CO": "Danske Bank",
    "MAERSK-B.CO": "Mærsk B",
    "VWS.CO": "Vestas",
    "GMAB.CO": "Genmab",
    "CARL-B.CO": "Carlsberg",
    "ORSTED.CO": "Ørsted",
    "COLO-B.CO": "Coloplast",
    "PNDORA.CO": "Pandora",
    "NSIS-B.CO": "Novonesis",
    "TRYG.CO": "Tryg",
    "DEMANT.CO": "Demant",
    "MAERSK-A.CO": "Mærsk A",
    "NDA-DK.CO": "Nordea",
    "JYSK.CO": "Jyske Bank",
    "ISS.CO": "ISS",
    "NKT.CO": "NKT",
    "ROCK-B.CO": "Rockwool",
    "ZEAL.CO": "Zealand Pharma",
}

LEADING_SWEDEN = {
    "VOLV-B.ST": "Volvo",
    "ATCO-A.ST": "Atlas Copco",
    "INVE-B.ST": "Investor",
    "AZN.ST": "AstraZeneca",
    "ERIC-B.ST": "Ericsson",
    "HM-B.ST": "H&M",
    "SEB-A.ST": "SEB",
    "SAND.ST": "Sandvik",
    "ABB.ST": "ABB",
    "SWED-A.ST": "Swedbank",
    "ASSA-B.ST": "Assa Abloy",
    "HEXA-B.ST": "Hexagon",
    "EQT.ST": "EQT",
    "SAAB-B.ST": "Saab",
    "SHB-A.ST": "Handelsbanken",
    "EPI-A.ST": "Epiroc",
    "ALFA.ST": "Alfa Laval",
    "ESSITY-B.ST": "Essity",
    "BOL.ST": "Boliden",
    "TELIA.ST": "Telia",
}

LEADING_NORWAY = {
    "EQNR.OL": "Equinor",
    "DNB.OL": "DNB",
    "MOWI.OL": "Mowi",
    "NHY.OL": "Norsk Hydro",
    "TEL.OL": "Telenor",
    "KOG.OL": "Kongsberg Gruppen",
    "AKRBP.OL": "Aker BP",
    "ORK.OL": "Orkla",
    "YAR.OL": "Yara",
    "STB.OL": "Storebrand",
    "SUBC.OL": "Subsea 7",
    "GJF.OL": "Gjensidige",
    "VAR.OL": "Vår Energi",
    "SALM.OL": "SalMar",
    "FRO.OL": "Frontline",
    "NOD.OL": "Nordic Semiconductor",
    "AKER.OL": "Aker",
    "TGS.OL": "TGS",
    "TOM.OL": "Tomra",
    "VEND.OL": "Vend Marketplaces",
}

LEADING_UNITED_STATES = {
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
    "GOOGL": "Alphabet",
    "AMZN": "Amazon",
    "META": "Meta",
    "BRK-B": "Berkshire Hathaway",
    "LLY": "Eli Lilly",
    "AVGO": "Broadcom",
    "JPM": "JPMorgan",
    "V": "Visa",
    "UNH": "UnitedHealth",
    "XOM": "Exxon Mobil",
    "JNJ": "Johnson & Johnson",
    "MA": "Mastercard",
    "COST": "Costco",
    "HD": "Home Depot",
    "PG": "Procter & Gamble",
    "NFLX": "Netflix",
    "TSLA": "Tesla",
}

LEADING_UNITED_KINGDOM = {
    "AZN.L": "AstraZeneca",
    "SHEL.L": "Shell",
    "HSBA.L": "HSBC",
    "ULVR.L": "Unilever",
    "BP.L": "BP",
    "RIO.L": "Rio Tinto",
    "GSK.L": "GSK",
    "DGE.L": "Diageo",
    "REL.L": "RELX",
    "BATS.L": "British American Tobacco",
    "LSEG.L": "London Stock Exchange",
    "NG.L": "National Grid",
    "AHT.L": "Ashtead",
    "BA.L": "BAE Systems",
    "CPG.L": "Compass",
    "EXPN.L": "Experian",
    "III.L": "3i",
    "AAL.L": "Anglo American",
    "GLEN.L": "Glencore",
    "LLOY.L": "Lloyds",
}

LEADING_GERMANY = {
    "SAP.DE": "SAP",
    "SIE.DE": "Siemens",
    "ALV.DE": "Allianz",
    "DTE.DE": "Deutsche Telekom",
    "AIR.DE": "Airbus",
    "MBG.DE": "Mercedes-Benz",
    "BMW.DE": "BMW",
    "VOW3.DE": "Volkswagen",
    "BAS.DE": "BASF",
    "BAYN.DE": "Bayer",
    "MUV2.DE": "Munich Re",
    "IFX.DE": "Infineon",
    "DB1.DE": "Deutsche Börse",
    "ADS.DE": "Adidas",
    "RHM.DE": "Rheinmetall",
    "DHL.DE": "DHL",
    "HEN3.DE": "Henkel",
    "SHL.DE": "Siemens Healthineers",
    "EOAN.DE": "E.ON",
    "MRK.DE": "Merck",
}

LEADING_FRANCE = {
    "MC.PA": "LVMH",
    "OR.PA": "L'Oréal",
    "TTE.PA": "TotalEnergies",
    "RMS.PA": "Hermès",
    "SAN.PA": "Sanofi",
    "AIR.PA": "Airbus",
    "SU.PA": "Schneider Electric",
    "AI.PA": "Air Liquide",
    "BNP.PA": "BNP Paribas",
    "EL.PA": "EssilorLuxottica",
    "SAF.PA": "Safran",
    "CS.PA": "AXA",
    "DG.PA": "Vinci",
    "KER.PA": "Kering",
    "CAP.PA": "Capgemini",
    "ORA.PA": "Orange",
    "BN.PA": "Danone",
    "RI.PA": "Pernod Ricard",
    "DSY.PA": "Dassault Systèmes",
    "HO.PA": "Thales",
}


MARKET_GROUPS: dict[str, tuple[dict[str, str], ...]] = {
    "denmark": (FREE_DENMARK, OMXC25, LEADING_DENMARK),
    "sweden": (FREE_SWEDEN, OMXS30, LEADING_SWEDEN),
    "norway": (FREE_NORWAY, OBX, LEADING_NORWAY),
    "united states": (LEADING_UNITED_STATES,),
    "united kingdom": (LEADING_UNITED_KINGDOM,),
    "germany": (LEADING_GERMANY,),
    "france": (LEADING_FRANCE,),
}

_TICKER_COUNTRY: dict[str, str] = {}
for _country, _groups in MARKET_GROUPS.items():
    for _group in _groups:
        for _ticker in _group:
            _TICKER_COUNTRY.setdefault(_ticker, _country)


def market_of(ticker: str) -> str | None:
    return _TICKER_COUNTRY.get(ticker)


def countries_in(tier: str) -> frozenset[str]:
    allowed = stocks_for(tier)
    return frozenset(country for ticker in allowed if (country := market_of(ticker)))


def _merge(*groups: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for group in groups:
        merged.update(group)
    return merged


def stocks_for(tier: str) -> dict[str, str]:
    """Return ticker -> name for a tier. Each tier includes every lower tier."""
    key = tier.strip().lower()
    if key == "free":
        return _merge(FREE_DENMARK, FREE_SWEDEN, FREE_NORWAY)
    if key == "nordic":
        return _merge(stocks_for("free"), OMXC25, OMXS30, OBX)
    if key == "international":
        return _merge(
            stocks_for("nordic"),
            LEADING_DENMARK,
            LEADING_SWEDEN,
            LEADING_NORWAY,
            LEADING_UNITED_STATES,
            LEADING_UNITED_KINGDOM,
            LEADING_GERMANY,
            LEADING_FRANCE,
        )
    raise KeyError(f"Unknown universe: {tier}")


def _check_hierarchy() -> None:
    free = set(stocks_for("free"))
    nordic = set(stocks_for("nordic"))
    international = set(stocks_for("international"))
    if not free <= nordic <= international:
        raise RuntimeError("Free must be included in Nordic, and Nordic in International.")


_check_hierarchy()
