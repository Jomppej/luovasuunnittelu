# Axolotl-sähkömittari

Pieni työpöydällä kelluva maskotti, joka näyttää Suomen pörssisähkön
hinnan ja vaihtaa tunnelmaansa sen mukaan:

| Hinta (snt/kWh) | Tunnelma     | Kuva                                  |
|------------------|-------------|----------------------------------------|
| < 5              | Halpa        | Iloinen axolotl villapaidassa, kaakaota |
| 5–15             | Kohtalainen  | Rento axolotl kukkaruukun kanssa        |
| > 15             | Kallis       | Palelava axolotl viltin ja kynttilän kanssa |

Hintarajat ovat muokattavissa tiedoston `main.py` alusta
(`CHEAP_MAX` ja `MODERATE_MAX`).

Hintatieto haetaan ilmaisesta [porssisahko.net](https://porssisahko.net)
-rajapinnasta, joka ei vaadi API-avainta, ja päivittyy 5 minuutin välein.

## Asennus (Windows / PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Käyttö

```powershell
python main.py
```

- **Siirtäminen:** raahaa maskottia hiiren vasemmalla painikkeella.
- **Sulkeminen / päivitys:** hiiren oikea painike maskotin päällä avaa valikon.

## Demo-tila (esitystä varten)

Jos haluat esitellä kaikki kolme tunnetilaa nopeasti ilman verkkoyhteyttä
(esim. esityksessä), avaa `main.py` ja aseta:

```python
DEMO_MODE = True
```

Käynnistä sen jälkeen ohjelma normaalisti (`python main.py`). Axolotl käy
tällöin automaattisesti läpi hinnat **4,0 / 10,0 / 20,0 snt/kWh** 
Kierto jatkuu loputtomiin, kunnes ikkuna
suljetaan. Hintatekstin perään ilmestyy `(DEMO)`-merkintä, jotta sen erottaa
demon oikeasta hinnasta. Hinnat ja näyttöaika ovat muokattavissa samasta
kohtaa tiedostoa (`DEMO_PRICES`, `DEMO_STEP_MS`). Muista vaihtaa
`DEMO_MODE` takaisin arvoon `False`, kun haluat palata oikeaan hintaan.

## Projektin rakenne

```
main.py         - käyttöliittymä (Tkinter), ikkunan logiikka
price_api.py    - pörssisähkön hinnan haku ja jäsennys
images/         - axolotl-kuvat eri tunnetiloille
requirements.txt
```

## Animaatio

Maskotti "leijuu" kevyesti ylös ja alas, jotta still-kuva ei näytä aivan
liikkumattomalta. Tämä on puhtaasti ohjelmallinen efekti, ei uusia piirrettyjä kuvia, tätä voi säätää `main.py`:n
`BOB_AMPLITUDE_PX`- ja `BOB_PERIOD_MS`-asetuksilla.

## Läpinäkyvyyden tekninen tausta

Ikkunan tausta tehdään läpinäkyväksi Tkinterin `-transparentcolor`-
ominaisuudella (vain Windows): yksi väri (kirkas magenta) piirretään
täysin läpinäkyvänä. Koska tämä toimii kaikki-tai-ei-mitään-periaatteella
eikä osaa sekoittaa puoliläpinäkyviä pikseleitä, kuvien alkuperäiset
pehmeät reunat "terävöitetään" ennen näyttöä (`_prepare_image` tiedostossa
`main.py`), jotta reunoille ei jää magentan sävyistä reunaviivaa.

Osana projektin suunnittelua ja yksittäisten koodiratkaisujen hahmottelua hyödynnettiin tekoälyavusteisia työkaluja. Tekoälyä ei käytetty itsenäisenä tuottajana, vaan kaikki ratkaisut, koodi ja sisältö on arvioitu, muokattu ja hyväksytty tekijän toimesta.
