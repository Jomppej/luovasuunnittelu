"""
Axolotl-sähkömittari

Pieni työpöydällä kelluva maskotti, joka vaihtaa tunnelmaansa Suomen
pörssisähkön hinnan mukaan:

  - halpa       -> iloinen axolotl villapaidassa, kaakaokuppi kädessä
  - kohtalainen -> rento axolotl kukkaruukun kanssa
  - kallis      -> palelava axolotl viltin ja kynttilän kanssa

Käynnistys:  python main.py
Siirtäminen: raahaa maskottia hiiren vasemmalla painikkeella
Sulkeminen:  hiiren oikea painike maskotin päällä -> Sulje

Demo-tila (esim. esitystä varten, ei vaadi verkkoyhteyttä):
  Aseta alla DEMO_MODE = True ja käynnistä ohjelma normaalisti. Axolotl
  käy tällöin automaattisesti läpi kaikki kolme tunnetilaa DEMO_PRICES-
  listan hinnoilla, kukin näkyvissä DEMO_STEP_MS ajan, ja kierto jatkuu
  loputtomiin kunnes ikkuna suljetaan.
"""
from __future__ import annotations

import ctypes
import math
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from PIL import Image, ImageTk

from price_api import PriceFetchError, fetch_current_price

try:
    # Windows skaalaa oletuksena "DPI-tietämättömien" ohjelmien ikkunoita
    # automaattisesti HiDPI-näytöillä (esim. 150 % skaalaus), mikä tekee
    # Tkinterin omista näyttömitoista (winfo_screenwidth/height) ja
    # ikkunan sijoittelusta epätarkkaa. Tämä kutsu merkitsee prosessin
    # DPI-tietoiseksi, jolloin koot ja sijainnit täsmäävät oikeisiin
    # näytön pikseleihin. Ei vaikuta mitään, jos alusta ei ole Windows tai
    # Windows-versio on hyvin vanha , silloin vain
    # ohitetaan virhe ja jatketaan normaalisti.
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except (AttributeError, OSError):
    pass

# --- Hinta-asetukset -----------------------------------------------------
# Rajat ovat senttiä/kWh. Esim. CHEAP_MAX = 5.0 tarkoittaa, että
# alle 5 snt/kWh hinta näytetään "halpana".
CHEAP_MAX = 5.0       # hinta < CHEAP_MAX               -> "halpa"
MODERATE_MAX = 15.0   # CHEAP_MAX <= hinta < MODERATE_MAX -> "kohtalainen"
#                        hinta >= MODERATE_MAX             -> "kallis"

# Kuinka usein (millisekunteina) oikea hinta haetaan verkosta uudelleen.
# Pörssisähkön hinta vaihtuu kerran tunnissa, joten 10 minuuttia riittää
# hyvin pitämään näytön ajan tasalla kuormittamatta rajapintaa.
UPDATE_INTERVAL_MS = 10 * 60 * 1000

# --- Demo-asetukset --------------------------------------------------------
# Demotilassa EI haeta oikeaa hintaa verkosta, vaan kierretään alla oleva
# kiinteä hintalista läpi
#
# Käyttö: vaihda DEMO_MODE arvoon True ja käynnistä "python main.py".
DEMO_MODE = False

# Hinnat (snt/kWh), jotka demo käy läpi järjestyksessä ja sitten alusta
# uudelleen: 4 -> halpa, 10 -> kohtalainen, 20 -> kallis.
DEMO_PRICES = [4.0, 10.0, 20.0]

# Kuinka kauan (millisekunteina) yksi demo-hinta näkyy ennen seuraavaan
DEMO_STEP_MS = 10 * 1000

# --- Ulkoasu-asetukset 
# Kansio, josta axolotl-kuvat löytyvät, ja koko (pikseleinä) johon ne
# skaalataan ikkunaa varten.
IMAGE_DIR = Path(__file__).parent / "images"
IMAGE_SIZE = (220, 220)

# Väri, joka tehdään ikkunasta läpinäkyväksi
# Kirkas magenta on hyvä valinta, koska se ei esiinny axolotl-kuvissa.
TRANSPARENT_COLOR = "#ff00ff"
# Sama väri (r, g, b)-lukuina Pillow'ta varten, ks. _prepare_image().
_TRANSPARENT_RGB = tuple(int(TRANSPARENT_COLOR[i : i + 2], 16) for i in (1, 3, 5))

# Alpha-arvo (0-255), josta alkaen reunapikseli lasketaan näkyväksi
# kokonaan eikä läpinäkyväksi, ks. _prepare_image().
_ALPHA_THRESHOLD = 128

# Mitä kuvatiedostoa käytetään kullekin tunnetilalle.
MOOD_IMAGES = {
    "halpa": IMAGE_DIR / "happy.png",
    "kohtalainen": IMAGE_DIR / "neutral.png",
    "kallis": IMAGE_DIR / "sad.png",
}

# --- Animaatioasetukset 
# Meillä on vain yksi still-kuva per tunnetila
# sen sijaan aksolottu saa kevyen, puhtaasti ohjelmallisen "leijunta"-liikkeen:
# kuva kelluu hitaasti ylös ja alas sinikäyrän mukaan
BOB_AMPLITUDE_PX = 6     # kuinka monta pikseliä ylös/alas liikutaan
BOB_PERIOD_MS = 2600     # yhden täyden edestakaisen liikkeen kesto
ANIMATION_FRAME_MS = 40  # ruudunpäivitysväli (~25 kuvaa/s)


def _prepare_image(path: Path) -> Image.Image:
    """Lataa axolotl-kuvan ja valmistelee sen chroma key -läpinäkyvyyttä varten.

    Tausta: Tkinterin "-transparentcolor" tekee läpinäkyväksi VAIN pikselit,
    jotka ovat TARKALLEEN TRANSPARENT_COLORin väriset, se ei osaa käsitellä
    puoliläpinäkyviä pikseleitä. Alkuperäisten PNG-kuvien pehmeät,
    antialiasoidut reunat sisältävät juuri tällaisia puoliläpinäkyviä
    pikseleitä. Kun Tkinterin Canvas piirtää ne, se sekoittaa ne taustaväriin
    (magenta) ja koska sekoitettu pikseli ei enää täsmää tarkalleen
    avainväriin, Windows ei tee siitä läpinäkyvää. Lopputulos näkyy
    näytöllä kirkkaana liila/pinkkinä reunaviivana axolotlin ääriviivan
    tuntumassa.

    Korjaus kahdessa vaiheessa:
      1. Alpha-kanava "terävöitetään": jokainen pikseli joko täysin näkyväksi
         (alpha=255) tai täysin läpinäkyväksi (alpha=0), ei mitään siltä
         väliltä. Tämä poistaa itse ongelman lähteen (puoliläpinäkyvyyden).
      2. Läpinäkyväksi jäävät pikselit korvataan suoraan tarkalla
         avainvärillä, jotta Tkinterin Canvas ei pääse enää sekoittamaan
         mitään - se saa valmiiksi joko axolotlin oman värin tai avainvärin.

    Tuloksena jokainen pikseli on joko axolotlin oma väri täysin peittävänä
    tai tarkalleen TRANSPARENT_COLORia, joten reunaviivaa ei enää synny.
    Kääntöpuolena reunan pehmennys häviää
    """
    img = Image.open(path).convert("RGBA").resize(IMAGE_SIZE, Image.Resampling.LANCZOS)

    _, _, _, alpha = img.split()
    sharp_alpha = alpha.point(lambda a: 255 if a >= _ALPHA_THRESHOLD else 0)
    img.putalpha(sharp_alpha)

    flattened = Image.new("RGBA", img.size, _TRANSPARENT_RGB + (255,))
    flattened.paste(img, (0, 0), img)  # img itse alpha-kanavaa käytetään maskina
    return flattened


def classify_price(price: float) -> str:
    """Luokittelee senttihinnan yhdeksi kolmesta tunnetilasta.

    Args:
        price: Sähkön hinta senttiä/kWh.

    Returns:
        Jokin avaimista "halpa", "kohtalainen" tai "kallis" - käytetään
        suoraan MOOD_IMAGES-sanakirjan avaimena oikean kuvan valintaan.
    """
    if price < CHEAP_MAX:
        return "halpa"
    if price < MODERATE_MAX:
        return "kohtalainen"
    return "kallis"


class AxolotlWidget:
    # pylint: disable=too-many-instance-attributes
    # Kaikki tila (ikkuna, kuvat, raahaus, demo- ja animaatiolaskurit) kuuluu
    # luontevasti samaan pieneen widget-luokkaan, luokan pilkkominen vain
    # attribuuttimäärän pienentämiseksi tekisi koodista vaikeampilukuisen.
    """Kelluva, reunaton Tkinter-ikkuna, joka näyttää axolotl-maskotin.

    Vastuut:
      - Ikkunan ja Canvasin pystytys (koko, sijainti, läpinäkyvyys).
      - Kuvien lataus muistiin kertaalleen käynnistyksessä.
      - Hiiritapahtumat: raahaus vasemmalla napilla, oikean napin valikko.
      - Hinnan päivityssilmukka (joko oikea rajapinta tai demo-hinnat).
      - leijunta animaatio.
    """

    def __init__(self) -> None:
        # Instanssimuuttujat alustetaan heti tässä (eikä vasta myöhemmissä
        # apumetodeissa), jotta kaikki luokan tila näkyy yhdestä paikasta -
        # helpottaa koodin lukemista ja on myös linttereiden suosittelema tapa.
        self._drag_offset = (0, 0)
        self._demo_index = 0
        self._anim_start = time.monotonic()  # animaation ajanotto, ks. _animate

        self.root = tk.Tk()
        self.root.title("Axolotl-sähkömittari")

        # overrideredirect(True) poistaa ikkunan otsikkopalkin ja reunukset
        # kokonaan, jolloin jäljelle jää vain itse piirretty sisältö.
        self.root.overrideredirect(True)

        # Pitää ikkunan aina muiden ikkunoiden päällä ("aina päällimmäisenä").
        self.root.attributes("-topmost", True)

        # Tämä on Windows-kohtainen Tkinter-ominaisuus: kaikki pikselit,
        # jotka ovat tätä väriä, piirretään täysin läpinäkyvinä. Koska
        # sekä ikkunan että Canvasin taustaväriksi asetetaan sama väri,
        # vain axolotl-kuva ja teksti jäävät näkyviin.
        self.root.attributes("-transparentcolor", TRANSPARENT_COLOR)
        self.root.configure(bg=TRANSPARENT_COLOR)

        # Ikkunan koko: kuvan koko + marginaalia tekstille alareunaan.
        width, height = IMAGE_SIZE[0] + 20, IMAGE_SIZE[1] + 50

        # Geometria-merkkijonon muoto on "LEVEYSxKORKEUS±X±Y". Etumerkki
        # "-" ennen X/Y:tä tarkoittaa, että sijainti lasketaan näytön
        # OIKEASTA/ALAREUNASTA eikä vasemmasta yläkulmasta. "-40-80"
        # tarkoittaa siis: 40 px näytön oikeasta reunasta, 80 px
        # alareunasta (jättää tilaa tehtäväpalkille). Tämä muoto antaa
        # ikkunointijärjestelmän itse laskea oikean sijainnin, mikä toimii
        # luotettavammin skaalauksen kanssa kuin itse laskettu
        # winfo_screenwidth()/height()-pohjainen sijainti.
        self.root.geometry(f"{width}x{height}-40-80")

        self.canvas = tk.Canvas(
            self.root,
            width=width,
            height=height,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,  # ei vaaleaa fokusreunusta Canvasin ympärille
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        # Kuvat ladataan ja skaalataan kertaalleen käynnistyksessä, ja
        # pidetään muistissa koko ohjelman ajan
        self._images: dict[str, ImageTk.PhotoImage] = {}
        self._load_images()

        # Axolotl-kuva keskelle Canvasia (hieman ylös, jotta tekstille
        # jää tilaa alareunaan). Keski-x ja lepo-y talletetaan, koska
        # _animate() tarvitsee niitä laskeakseen leijunta-animaation
        # poikkeaman alkuperäisestä paikasta joka ruudulla.
        self._center_x = width // 2
        self._image_base_y = IMAGE_SIZE[1] // 2 + 5
        self.image_item = self.canvas.create_image(
            self._center_x, self._image_base_y, image=self._images["kohtalainen"]
        )

        # Hintateksti piirretään NELJÄÄN KERTAAN mustana, 1 pikselin verran
        # joka suuntaan siirrettynä (ylös/alas/vasen/oikea), ja vasta
        # tämän "ääriviivan" päälle varsinainen valkoinen teksti. Tämä on
        # yksinkertainen tapa saada teksti luettavaksi sekä
        # vaalean että tumman työpöytätaustan päällä ilman erillistä
        # taustalaatikkoa.
        self.text_item = self.canvas.create_text(
            width // 2,
            height - 16,
            text="Haetaan hintaa...",
            fill="white",
            font=("Segoe UI", 11, "bold"),
        )
        self.text_outline_items = [
            self.canvas.create_text(
                width // 2 + dx,
                height - 16 + dy,
                text="Haetaan hintaa...",
                fill="black",
                font=("Segoe UI", 11, "bold"),
            )
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1))
        ]
        # Varmistetaan, että valkoinen pääteksti piirtyy ääriviivan päälle
        # (create_text-kutsujen järjestys määrää oletuspiirtojärjestyksen,
        # mutta tämä tekee riippuvuuden eksplisiittiseksi ja turvalliseksi).
        self.canvas.tag_raise(self.text_item)

        self._make_draggable()
        self._make_context_menu()

        # Käynnistetään joko demo-kierto tai oikea hinnanhakusilmukka, sekä
        # erikseen leijunta-animaatio. Kaikki kolme ajastavat itse itsensä
        # uudelleen Tkinterin after()-mekanismilla, joten niitä kutsutaan
        # ulkopuolelta vain tässä, kertaalleen.
        if DEMO_MODE:
            self._run_demo_step()
        else:
            self.update_price()
        self._animate()

    def _load_images(self) -> None:
        """Lataa jokaisen tunnetilan kuvan levyltä ja valmistelee sen näyttöä varten.

        Tulos tallennetaan self._images-sanakirjaan, jotta kuvaa ei
        tarvitse ladata/skaalata uudelleen joka kerta kun tunnetila
        vaihtuu, vain valmiiksi ladattu PhotoImage-olio vaihdetaan
        Canvasin kuvaelementtiin. Ks. _prepare_image() reunaväri-
        käsittelyn selitys.
        """
        for mood, path in MOOD_IMAGES.items():
            self._images[mood] = ImageTk.PhotoImage(_prepare_image(path))

    def _make_draggable(self) -> None:
        """Sitoo hiiritapahtumat, joilla maskottia voi raahata.

        Koska ikkunalla ei ole otsikkopalkkia (overrideredirect), Windows
        ei osaa raahata sitä automaattisesti 
          1. Hiiren painalluksesta (ButtonPress) muistetaan, mihin kohtaan
             Canvasia käyttäjä tarttui (_drag_offset).
          2. Jokaisella hiiren liikkeellä painike pohjassa (B1-Motion)
             lasketaan ikkunan uusi vasen-ylä-kulma: hiiren NYKYINEN
             sijainti koko näytöllä (winfo_pointerx/y) miinus tartunta-
             kohdan offset. Näin ikkuna "seuraa" hiirtä luontevasti
             riippumatta siitä, mistä kohtaa maskottia tartuttiin kiinni.
        """

        def on_press(event: tk.Event) -> None:
            self._drag_offset = (event.x, event.y)

        def on_drag(_event: tk.Event) -> None:
            x = self.root.winfo_pointerx() - self._drag_offset[0]
            y = self.root.winfo_pointery() - self._drag_offset[1]
            self.root.geometry(f"+{x}+{y}")

        self.canvas.bind("<ButtonPress-1>", on_press)
        self.canvas.bind("<B1-Motion>", on_drag)

    def _make_context_menu(self) -> None:
        """Luo hiiren oikealla painikkeella avautuvan pikavalikon.

        Valikossa on kaksi vaihtoehtoa: hae hinta heti uudelleen, tai
        sulje ohjelma. Koska ikkunalla ei ole otsikkopalkkia eikä siten
        tavallista sulkupainiketta, tämä on ainoa tapa sulkea ohjelma
        hiirellä
        """
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Päivitä nyt", command=self.update_price)
        menu.add_separator()
        menu.add_command(label="Sulje", command=self.root.destroy)

        def show_menu(event: tk.Event) -> None:
            menu.tk_popup(event.x_root, event.y_root)

        self.canvas.bind("<Button-3>", show_menu)

    def _set_text(self, text: str) -> None:
        """Päivittää sekä näkyvän hintatekstin että sen mustan ääriviivan."""
        self.canvas.itemconfig(self.text_item, text=text)
        for item in self.text_outline_items:
            self.canvas.itemconfig(item, text=text)

    def _show_price(self, price: float, *, suffix: str = "") -> None:
        """Päivittää axolotl-kuvan ja hintatekstin annetun hinnan mukaan.

        Yhteinen apumetodi, jota käyttävät sekä oikea hinnanhaku
        (update_price) että demo-kierto (_run_demo_step), jotta itse
        "näytä tämä hinta ruudulla" -logiikka on vain yhdessä paikassa.

        Args:
            price: Näytettävä hinta senttiä/kWh.
            suffix: Valinnainen teksti hinnan perään (esim. " (DEMO)").
        """
        mood = classify_price(price)
        self.canvas.itemconfig(self.image_item, image=self._images[mood])
        self._set_text(f"{price:.1f} snt/kWh{suffix}")

    def update_price(self) -> None:
        """Hakee nykyisen hinnan rajapinnasta ja päivittää näytön.

        Jos haku epäonnistuu (ei verkkoa, rajapinta nurin tms.), kuva
        jätetään ennalleen ja tekstiksi vaihtuu virheilmoitus, ohjelma
        ei siis kaadu tilapäisen verkko-ongelman takia.

        Ajastaa itsensä automaattisesti ajamaan uudelleen UPDATE_INTERVAL_MS
        millisekunnin päästä (Tkinterin after()-mekanismilla), joten tätä
        kutsutaan ulkopuolelta vain kerran käynnistyksessä.
        """
        try:
            info = fetch_current_price()
            self._show_price(info.price)
        except PriceFetchError:
            self._set_text("Hintaa ei saatavilla")

        self.root.after(UPDATE_INTERVAL_MS, self.update_price)

    def _run_demo_step(self) -> None:
        """Näyttää demo-listan seuraavan hinnan ja ajastaa seuraavan askeleen.

        Käydään DEMO_PRICES-lista läpi järjestyksessä ja aloitetaan
        automaattisesti alusta listan lopussa (modulo-operaattori %),
        joten demo voi pyöriä vaikka koko esityksen ajan ilman että
        kukaan koskee ohjelmaan. Ei tarvitse verkkoyhteyttä.
        """
        price = DEMO_PRICES[self._demo_index % len(DEMO_PRICES)]
        self._demo_index += 1

        self._show_price(price, suffix=" (DEMO)")

        self.root.after(DEMO_STEP_MS, self._run_demo_step)

    def _animate(self) -> None:
        """Liikuttaa axolotl-kuvaa kevyesti ylös ja alas sinikäyrän mukaan.
        Puhtaasti visuaalinen "leijunta"-efekti.
        """
        elapsed_ms = (time.monotonic() - self._anim_start) * 1000
        phase = (elapsed_ms / BOB_PERIOD_MS) * 2 * math.pi
        offset = BOB_AMPLITUDE_PX * math.sin(phase)

        self.canvas.coords(self.image_item, self._center_x, self._image_base_y + offset)

        self.root.after(ANIMATION_FRAME_MS, self._animate)

    def run(self) -> None:
        """Käynnistää Tkinterin tapahtumasilmukan (pysäyttää tämän funktion
        suorituksen, kunnes ikkuna suljetaan)."""
        self.root.mainloop()


def main() -> None:
    """Ohjelman käynnistyspiste: tarkistaa kuvat ja käynnistää widgetin."""
    missing = [path for path in MOOD_IMAGES.values() if not path.exists()]
    if missing:
        names = ", ".join(p.name for p in missing)
        messagebox.showerror(
            "Axolotl-sähkömittari",
            f"Kuvatiedostoja puuttuu images-kansiosta: {names}",
        )
        return

    AxolotlWidget().run()


if __name__ == "__main__":
    main()
