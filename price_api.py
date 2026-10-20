"""
Pörssisähkön hintatiedon haku.

Tämä moduuli hoitaa yhteyden ilmaiseen porssisahko.net-rajapintaan ja
palauttaa Suomen Nord Pool -spot-hinnan kuluvalle tunnille. Rajapinta ei
vaadi API-avainta, ja se sisältää sekä kuluvan että tulevien

Rajapinnan palauttama JSON näyttää yksinkertaistettuna tältä::

    {
        "prices": [
            {
                "price": 8.49,
                "startDate": "2026-10-12T21:00:00.000Z",
                "endDate": "2026-10-12T22:00:00.000Z"
            },
            ...
        ]
    }

- ``price``     : senttiä/kWh, sisältää arvonlisäveron.
- ``startDate``/``endDate`` : tunnin alku- ja loppuhetki UTC-ajassa.
Oikea rivi kuluvalle hetkelle etsitään käymällä lista läpi ja valitsemalla
se, jonka aikaväliin ``datetime.now()`` osuu.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import requests

# Rajapinnan osoite. Ei vaadi API-avainta eikä rekisteröitymistä.
API_URL = "https://api.porssisahko.net/v1/latest-prices.json"

# Kuinka kauan (sekuntia) odotetaan rajapinnan vastausta, ennen kuin
# haku katsotaan epäonnistuneeksi. Pidetään lyhyenä, ettei käyttöliittymä
# jää hetkeksikään jumiin huonon verkkoyhteyden takia.
REQUEST_TIMEOUT = 5


class PriceFetchError(Exception):
    """Hinnan hakeminen tai jäsentäminen epäonnistui.

    Nostetaan aina kun jotain menee pieleen rajapinnan kanssa: ei
    verkkoyhteyttä, rajapinta vastaa virheellä, data on odottamattomassa
    muodossa, tai kuluvalle hetkelle ei yksinkertaisesti löydy hintaa.
    Kutsujan (main.py) ei tarvitse tietää tarkkaa syytä, vaan riittää käsitellä
    tämä yksi poikkeustyyppi.
    """


@dataclass
class PriceInfo:
    """Yhden tunnin pörssisähkön hintatieto."""

    price: float        # senttiä/kWh, sisältää ALV:n
    start: dt.datetime  # tunnin alkuhetki (UTC, aikavyöhyketietoinen)
    end: dt.datetime    # tunnin loppuhetki (UTC, aikavyöhyketietoinen)


def _parse_time(value: str) -> dt.datetime:
    """Muuntaa rajapinnan ISO 8601 -aikaleiman (esim. ``"...Z"``) datetimeksi.

    ``datetime.fromisoformat`` ei ennen Python 3.11:tä osaa tulkita
    "Z"-loppuista UTC-merkintää suoraan, joten se korvataan ensin
    standardimuotoisella ``+00:00``-aikavyöhykkeellä. 
    """
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_current_price() -> PriceInfo:
    """Hakee ja palauttaa kuluvan tunnin pörssisähkön hinnan.

    Returns:
        PriceInfo-olio, jonka ``price``-kenttä on senttiä/kWh

    Raises:
        PriceFetchError: jos rajapintaan ei saada yhteyttä, se vastaa
            virheellä, data on odottamattomassa muodossa, tai kuluvalle
            hetkelle ei löydy hintaa palautetusta listasta.
    """
    try:
        response = requests.get(API_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()  # nostaa HTTPError-poikkeuksen esim. 500/404
        entries = response.json()["prices"]
    except (requests.RequestException, ValueError, KeyError) as exc:
        # requests.RequestException: ei verkkoyhteyttä / aikakatkaisu / HTTP-virhe
        # ValueError: vastaus ei ollut kelvollista JSONia
        # KeyError: JSON ei sisältänyt odotettua "prices"-avainta
        raise PriceFetchError("Hintatiedon haku rajapinnasta epäonnistui") from exc

    now = dt.datetime.now(dt.timezone.utc)
    for entry in entries:
        start = _parse_time(entry["startDate"])
        end = _parse_time(entry["endDate"])
        if start <= now < end:
            return PriceInfo(price=entry["price"], start=start, end=end)

    # Tämä on hyvin epätodennäköistä normaalikäytössä (rajapinta kattaa
    # aina kuluvan hetken)
    raise PriceFetchError("Nykyistä hintaa ei löytynyt rajapinnan datasta")
