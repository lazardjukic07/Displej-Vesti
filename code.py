import time
import board
import wifi
import socketpool
import ssl
import json
import adafruit_requests
import adafruit_ntp
import displayio
import framebufferio
import rgbmatrix
import microcontroller

from custom_font_statički import CUSTOM_FONT
from config import WIFI_SSID, WIFI_PASSWORD, UTC_OFFSET

# ============================================================
# OSLOBAĐANJE DISPLEJA
# ============================================================
displayio.release_displays()

# ============================================================
# HUB75 128x64 MATRIX
# ============================================================
matrix = rgbmatrix.RGBMatrix(
    width=128,
    height=64,
    bit_depth=6,
    rgb_pins=[
        board.GP2, board.GP3, board.GP6,
        board.GP7, board.GP8, board.GP9
    ],
    addr_pins=[
        board.GP10, board.GP16, board.GP18,
        board.GP20, board.GP21
    ],
    clock_pin=board.GP11,
    latch_pin=board.GP12,
    output_enable_pin=board.GP13,
    tile=1,
    serpentine=False
)

display = framebufferio.FramebufferDisplay(matrix, auto_refresh=False)

# ============================================================
# DISPLAYIO GRUPA I BITMAP
# ============================================================
group = displayio.Group()

font_bitmap = displayio.Bitmap(
    128,
    64,
    6
)

font_palette = displayio.Palette(6)

font_palette[0] = 0x000000
font_palette[1] = 0x00FFFF  # Cijan
font_palette[2] = 0x808080  # Siva
font_palette[3] = 0x00FF00  # BRG Crvena
font_palette[4] = 0x0000FF
font_palette[5] = 0xFF0000

font_tilegrid = displayio.TileGrid(
    font_bitmap,
    pixel_shader=font_palette,
    x=0,
    y=0
)

group.append(font_tilegrid)

CHAR_WIDTH = 5
CHAR_SPACING = 1
WORD_SPACING = 2
DOT_WIDTH = 2


def clear_custom_area(x1, y1, x2, y2):
    for y in range(y1, y2):
        for x in range(x1, x2):
            font_bitmap[x, y] = 0


# ============================================================
# PRORAČUN ŠIRINE TEKSTA
# ============================================================
def get_text_width(text):
    width = 0

    for char in text:
        if char == " ":
            width += WORD_SPACING

        elif char in (".", ":", ","):
            width += DOT_WIDTH + CHAR_SPACING

        elif char in CUSTOM_FONT:
            char_w = max(
                px for px, py in CUSTOM_FONT[char]
            ) + 1

            width += char_w + CHAR_SPACING

        elif char.isdigit():
            width += CHAR_WIDTH

        else:
            width += CHAR_WIDTH + CHAR_SPACING

    return width


# ============================================================
# CRTANJE CUSTOM TEKSTA
# ============================================================
def draw_custom_text(
    text,
    start_x,
    start_y,
    center=False,
    color_index=1
):
    x_position = start_x

    if center:
        text_width = get_text_width(text)
        x_position = (128 - text_width) // 2

    for char in text:

        if char == " ":
            x_position += WORD_SPACING
            continue

        if char in (".", ":", ","):

            if char in CUSTOM_FONT:
                for px, py in CUSTOM_FONT[char]:

                    x = x_position + px
                    y = start_y + py

                    if 0 <= x < 128 and 0 <= y < 64:
                        font_bitmap[x, y] = color_index

            x_position += DOT_WIDTH + CHAR_SPACING
            continue

        if char in CUSTOM_FONT:

            for px, py in CUSTOM_FONT[char]:

                x = x_position + px
                y = start_y + py

                if 0 <= x < 128 and 0 <= y < 64:
                    font_bitmap[x, y] = color_index

            char_w = max(
                px for px, py in CUSTOM_FONT[char]
            ) + 1

            x_position += char_w + CHAR_SPACING

        elif char.isdigit():
            x_position += CHAR_WIDTH

        else:
            x_position += CHAR_WIDTH + CHAR_SPACING


# ============================================================
# BOOT SCREEN
# ============================================================
display.root_group = group

clear_custom_area(0, 0, 128, 64)

draw_custom_text(
    "Kontrolna tabla",
    0,
    2,
    center=True,
    color_index=1
)

draw_custom_text(
    "by Lazar Đukić",
    0,
    16,
    center=True,
    color_index=2
)

draw_custom_text(
    "SN: IDS-S0001-PR1-V1.0",
    0,
    28,
    center=True,
    color_index=2
)

draw_custom_text(
    "+381652063576",
    0,
    38,
    center=True,
    color_index=2
)

draw_custom_text(
    " ",
    0,
    39,
    center=True,
    color_index=1
)

draw_custom_text(
    "Pokretanje softvera...",
    0,
    52,
    center=True,
    color_index=1
)

display.refresh()
time.sleep(4)

# ============================================================
# WIFI & NTP
# ============================================================
print("Povezujem se na Wi-Fi...")
wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
print("Wi-Fi povezan! IP:", wifi.radio.ipv4_address)

pool = socketpool.SocketPool(wifi.radio)

ssl_context = ssl.create_default_context()

requests = adafruit_requests.Session(
    pool,
    ssl_context
)

ntp = adafruit_ntp.NTP(
    pool,
    server="pool.ntp.org",
    tz_offset=0
)

# ============================================================
# VREMENSKA PROGNOZA - BEOGRAD
# ============================================================
weather_temp = "--°C"
weather_status = "N/A"
weather_min = "--°C"
weather_max = "--°C"

weather_last_update = 0
WEATHER_UPDATE_INTERVAL = 600


def get_weather():

    global weather_temp
    global weather_status
    global weather_min
    global weather_max

    try:

        print("Učitavam vreme...")

        sock = pool.socket(
            pool.AF_INET,
            pool.SOCK_STREAM
        )

        sock.connect(
            ("api.open-meteo.com", 80)
        )

        path = (
            "/v1/forecast?"
            "latitude=44.752472"
            "&longitude=20.448794"
            "&current=temperature_2m,weather_code"
            "&daily=temperature_2m_max,temperature_2m_min"
            "&timezone=Europe%2FBelgrade"
        )

        request = (
            "GET " + path + " HTTP/1.1\r\n"
            "Host: api.open-meteo.com\r\n"
            "User-Agent: CircuitPython\r\n"
            "Connection: close\r\n"
            "\r\n"
        )

        sock.send(
            request.encode("utf-8")
        )

        response = bytearray(8192)
        total = 0

        while total < len(response):

            try:

                n = sock.recv_into(
                    memoryview(response)[total:]
                )

                if n == 0:
                    break

                total += n

            except OSError:
                break

        sock.close()

        response_text = bytes(
            response[:total]
        ).decode(
            "utf-8",
            "ignore"
        )

        json_start = response_text.find("{")
        json_end = response_text.rfind("}")

        if json_start == -1 or json_end == -1:
            raise Exception("JSON struktura nije pronađena")

        json_text = response_text[
            json_start:json_end + 1
        ]

        data = json.loads(json_text)

        current = data["current"]

        temperature = current["temperature_2m"]
        weather_code = current["weather_code"]

        weather_max = "{:.0f}°C".format(
            data["daily"]["temperature_2m_max"][0]
        )

        weather_min = "{:.0f}°C".format(
            data["daily"]["temperature_2m_min"][0]
        )

        if weather_code == 0:
            weather_icon = "*"

        elif weather_code in (1, 2, 3):
            weather_icon = "$"

        elif weather_code in (45, 48):
            weather_icon = "%"

        elif weather_code in (
            51, 53, 55,
            56, 57,
            61, 63, 65,
            66, 67,
            80, 81, 82
        ):
            weather_icon = "@"

        else:
            weather_icon = "$"

        weather_temp = "{} {:.0f}°C".format(
            weather_icon,
            temperature
        )

        if weather_code == 0:
            weather_status = "Sunčano"

        elif weather_code in (1, 2, 3):
            weather_status = "Oblačno"

        elif weather_code in (45, 48):
            weather_status = "Magla"

        elif weather_code in (
            51, 53, 55,
            56, 57,
            61, 63, 65,
            66, 67
        ):
            weather_status = "Kiša"

        elif weather_code in (71, 73, 75, 77):
            weather_status = "Sneg"

        elif weather_code in (80, 81, 82):
            weather_status = "Pljusak"

        elif weather_code in (85, 86):
            weather_status = "Sneg"

        elif weather_code in (95, 96, 99):
            weather_status = "Grmljavina"

        else:
            weather_status = "Nepoznato"

    except Exception as e:

        print(
            "Greška pri vremenu:",
            e
        )
        raise e


display.root_group = group

clear_custom_area(
    0,
    0,
    128,
    64
)

display.refresh()

# ============================================================
# STANJA ALARMA I DATUM
# ============================================================
dani = [
    "pon",
    "uto",
    "sre",
    "čet",
    "pet",
    "sub",
    "ned"
]

meseci = [
    "jan",
    "feb",
    "mar",
    "apr",
    "maj",
    "jun",
    "jul",
    "avg",
    "sep",
    "okt",
    "nov",
    "dec"
]

alarm_enabled = False
alarm_hour = 7
alarm_minute = 0
is_expired = False

# ============================================================
# LISTA VESTI ZA ROTIRANJE (5 KOMADA)
# ============================================================
news_list = [
    [
        "Vesti - Finansije",
        "NBS: Osigurani depoziti",
        "zaštićeni, bankarski",
        "sektor stabilan.",
        "ekapija.com      1 od 5"
    ],
    [
        "Vesti - Tršište nekretnina",
        "Cene kvadrata stabilne,",
        "velika ponuda novih",
        "stanova u Beogradu.",
        "ekapija.com      2 od 5"
    ],
    [
        "Vesti - Parlament. izbori",
        "Raspoređeni mandati,",
        "Studentska lista - 140",
        "SNS - 103    Ostali - 7",
        "nova.rs      3 od 5"
    ],
    [
        "Vesti - Privreda",
        "Rast industrijske",
        "proizvodnje u prvom",
        "kvartalu ove godine.",
        "ekapija.com      4 od 5"
    ],
    [
        "Vesti - Infrastruktura",
        "Nastavak radova na",
        "modernizaciji pruga",
        "i auto-puteva.",
        "ekapija.com      5 od 5"
    ]
]
news_index = 0

# ============================================================
# GLAVna PETLJA
# ============================================================
last_second = -1

MESSAGE_INTERVAL = 9  # Vreme između prikaza (120 sekundi = 2 minuta)
MESSAGE_DURATION = 8   # Koliko dugo vest stoji na ekranu (10 sekundi)
last_message_time = time.monotonic()

try:
    get_weather()
except Exception as e:
    print("Greška pri inicijalnom pokretanju, resetujem se...", e)
    time.sleep(2)
    microcontroller.reset()

while True:
    try:
        current_time = time.monotonic()

        # ========================================================
        # PROVERA DA LI JE VREME ZA SLEDEĆU VEST U KRUGU
        # ========================================================
        if current_time - last_message_time >= MESSAGE_INTERVAL:
            clear_custom_area(0, 0, 128, 64)
            
            # Uzmi trenutnu vest iz liste na osnovu indeksa
            vest = news_list[news_index]
            
            draw_custom_text(vest[0], 0, 2, center=False, color_index=2)
            draw_custom_text(vest[1], 0, 13, center=False, color_index=1)
            draw_custom_text(vest[2], 0, 24, center=False, color_index=1)
            draw_custom_text(vest[3], 0, 35, center=False, color_index=1)
            draw_custom_text(vest[4], 0, 56, center=False, color_index=4)
            display.refresh()
            
            # Drži vest na ekranu 10 sekundi
            time.sleep(MESSAGE_DURATION)
            
            clear_custom_area(0, 0, 128, 64)
            display.refresh()
            
            # Pomeri indeks na sledeću vest (ako je stigao do 5, vrati na 0)
            news_index = (news_index + 1) % len(news_list)
            
            last_message_time = time.monotonic()
            last_second = -1

        # ========================================================
        # VREMENSKA PROGNOZA
        # ========================================================
        if (
            time.monotonic() - weather_last_update
            >= WEATHER_UPDATE_INTERVAL
        ):

            get_weather()

            weather_last_update = (
                time.monotonic()
            )

        # ========================================================
        # NTP VREME
        # ========================================================
        utc = ntp.datetime

        epoch = (
            time.mktime(utc)
            + (UTC_OFFSET * 3600)
        )

        now = time.localtime(epoch)

        # ========================================================
        # OSVEŽAVANJE DISPLEJA SVAKOG SEKUNDA
        # ========================================================
        if now.tm_sec != last_second:

            last_second = now.tm_sec

            # ----------------------------------------------------
            # DATUM I VREME - GORE LEVO
            # ----------------------------------------------------
            clear_custom_area(
                0,
                0,
                64,
                20
            )

            datum = "{}, {:02d}. {} {}.".format(
                dani[now.tm_wday],
                now.tm_mday,
                meseci[now.tm_mon - 1],
                now.tm_year
            )

            vreme_str = "{:02d}:{:02d}".format(
                now.tm_hour,
                now.tm_min
            )

            draw_custom_text(
                vreme_str,
                1,
                10,
                center=False,
                color_index=2
            )
            
            draw_custom_text(
                datum,
                1,
                1,
                center=False,
                color_index=2
            )
            
            draw_custom_text(
                "Petra Konjovića 12D",
                0,
                25,
                center=True,
                color_index=2
            )
            
            draw_custom_text(
                "_",
                112,
                54,
                center=False,
                color_index=3
            )
            
            draw_custom_text(
                "/",
                1,
                40,
                center=False,
                color_index=5
            )

            # ----------------------------------------------------
            # VREME - GORE DESNO
            # ----------------------------------------------------
            weather_line = weather_temp

            weather_width = get_text_width(
                weather_line
            )

            weather_x = (
                128 - weather_width
            )

            if weather_x < 65:
                weather_x = 65

            draw_custom_text(
                weather_line,
                weather_x,
                1,
                center=False
            )

            # ----------------------------------------------------
            # STATUS VREMENA
            # ----------------------------------------------------
            status_width = get_text_width(
                weather_status
            )

            status_x = max(
                65,
                128 - status_width
            )

            draw_custom_text(
                weather_status,
                status_x,
                10,
                center=False
            )

            display.refresh()

        time.sleep(0.02)

    except Exception as e:
        print("Došlo je do greške u radu sistema:", e)
        print("Restartujem uređaj za 3 sekunde...")
        time.sleep(3)
        microcontroller.reset()
