# -*- coding: utf-8 -*-
"""
DraveKITT Mobile - het KITT-dashboard voor Android (Kivy, touch).

- Voicebox in het midden (3 kolommen rode segmenten) met de ZIJKNOPPEN eromheen,
  net als de Windows-versie: TIJD/ACCU/SYSTEEM/GRAP/WEER links en
  HERHAAL/NIEUWS/NIEUW/SCAN/HULP rechts.
- Je typt of spreekt; KITT antwoordt en spreekt het uit (Androids stem, instelbaar).
- Het zware werk (groot model, zoeken, weer) kan via je pc-server ("hoofdkwartier").
  Geen verbinding? Dan een nette KITT-melding + lichte lokale antwoorden.
"""
import datetime
import json
import math
import os
import random
import socket
import threading

from kivy.app import App


def _open_url(url):
    """Webpagina openen in de browser van de telefoon (bv. de doneerpagina)."""
    try:
        from jnius import autoclass
        I = autoclass("android.content.Intent")
        i = I(I.ACTION_VIEW, autoclass("android.net.Uri").parse(url))
        i.addFlags(0x10000000)
        autoclass("org.kivy.android.PythonActivity").mActivity.startActivity(i)
    except Exception:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle
from kivy.network.urlrequest import UrlRequest
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner

Window.clearcolor = (0.043, 0.043, 0.055, 1)
# scherm schuift omhoog als het toetsenbord opkomt, zodat je het invoervak ziet
Window.softinput_mode = "below_target"

HQ_DOWN = "Ik kan op dit moment geen verbinding maken met het hoofdkwartier."

AMBER = (0.90, 0.72, 0.12, 1)
RED = (0.78, 0.16, 0.12, 1)
DARKTXT = (0.08, 0.06, 0.04, 1)

LEFT_BTNS = [("TIJD", AMBER), ("ACCU", AMBER), ("SYSTEEM", RED),
             ("GRAP", RED), ("WEER", RED)]
RIGHT_BTNS = [("HERHAAL", AMBER), ("NIEUWS", AMBER), ("NIEUW", RED),
              ("SCAN", RED), ("HULP", RED)]


# ===========================================================================
# Stem: Androids tekst-naar-spraak (instelbaar) met terugval op plyer
# ===========================================================================
class Voice:
    def __init__(self):
        self.rate = 1.0
        self.pitch = 1.0
        self.name = ""
        self._mode = "none"
        self._tts = None
        self._TTS = None
        try:
            from plyer import tts as _p
            self._plyer = _p
        except Exception:
            self._plyer = None

    def init_android(self):
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            self._TTS = autoclass("android.speech.tts.TextToSpeech")
            self._tts = self._TTS(PythonActivity.mActivity, None)
            self._mode = "android"
        except Exception:
            self._mode = "plyer" if self._plyer else "none"

    def _all_voice_names(self):
        names = []
        if self._mode == "android" and self._tts is not None:
            try:
                it = self._tts.getVoices().iterator()
                while it.hasNext():
                    names.append(it.next().getName())
            except Exception:
                pass
        return names

    def voice_options(self):
        """Alleen Nederlandse en Engelse stemmen, met nette namen.
        Geeft een lijst (label, voice_id) terug."""
        raw = self._all_voice_names()
        out = []

        def add(prefix, naam):
            group = [v for v in sorted(set(raw)) if v.lower().startswith(prefix)]
            for i, v in enumerate(group, 1):
                low = v.lower()
                tag = "lokaal" if "local" in low else ("online" if "network" in low else "")
                lbl = "%s %d%s" % (naam, i, (" (" + tag + ")" if tag else ""))
                out.append((lbl, v))
        add("nl", "Nederlands")
        add("en", "Engels")
        return out

    def default_dutch(self):
        for label, vid in self.voice_options():
            if label.startswith("Nederlands"):
                return vid
        return ""

    def speak(self, text):
        if not text:
            return
        if self._mode == "android" and self._tts is not None:
            try:
                self._tts.setSpeechRate(float(self.rate))
                self._tts.setPitch(float(self.pitch))
                if self.name:
                    it = self._tts.getVoices().iterator()
                    while it.hasNext():
                        v = it.next()
                        if v.getName() == self.name:
                            self._tts.setVoice(v)
                            break
                self._tts.speak(text, self._TTS.QUEUE_FLUSH, None, None)
                return
            except Exception:
                pass
        if self._plyer is not None:
            try:
                self._plyer.speak(message=text)
            except Exception:
                try:
                    self._plyer.speak(text)
                except Exception:
                    pass


VOICE = Voice()


def android_listen(on_text, on_fail):
    """Androids spraak-naar-tekst. on_text(tekst) / on_fail(reden)."""
    try:
        from jnius import autoclass
        from android import activity as act_module
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        current = PythonActivity.mActivity
        RecognizerIntent = autoclass("android.speech.RecognizerIntent")
        Intent = autoclass("android.content.Intent")
        intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "nl-NL")

        def _on_result(req, res, data):
            try:
                act_module.unbind(on_activity_result=_on_result)
            except Exception:
                pass
            try:
                if data is not None:
                    r = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
                    if r is not None and r.size() > 0:
                        on_text(r.get(0))
                        return
                on_fail("geen tekst herkend")
            except Exception as e:
                on_fail("resultaat: %s" % e)

        act_module.bind(on_activity_result=_on_result)
        current.startActivityForResult(intent, 4242)
    except Exception as e:
        on_fail("start: %s" % e)


# ===========================================================================
# Lokaal "brein" (terugval) + telefoon-functies
# ===========================================================================
def kitt_reply(text):
    t = (text or "").strip().lower()
    if not t:
        return "Ik luister."
    if any(w in t for w in ("hoe laat", "tijd", "klok")):
        return "Het is " + datetime.datetime.now().strftime("%H:%M") + " uur."
    if any(w in t for w in ("welke dag", "datum", "vandaag")):
        d = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag",
             "zaterdag", "zondag"]
        n = datetime.datetime.now()
        return "Het is %s %s." % (d[n.weekday()], n.strftime("%d-%m-%Y"))
    if any(w in t for w in ("hallo", "hoi", "hey", "goedemorgen", "goedemiddag")):
        return random.choice(["Hallo. Alle systemen functioneren naar behoren.",
                              "Goedendag. Waarmee kan ik van dienst zijn?",
                              "Ik sta tot je beschikking, zoals altijd."])
    if "hoe heet" in t or "wie ben j" in t or "je naam" in t:
        return "Ik ben KITT - de stem van Knight Industries. Tot je dienst."
    if any(w in t for w in ("dank", "bedankt", "thanks")):
        return "Graag gedaan."
    if any(w in t for w in ("grap", "mop")):
        return random.choice([
            "Een auto die niet remt kan z'n banden niet inhouden.",
            "Ik zou een grap over benzine maken, maar die is te vluchtig."])
    return random.choice(["Begrepen.", "Genoteerd. Mijn systemen verwerken het.",
                          "Interessant. Vertel eens meer."])


def phone_battery():
    try:
        from plyer import battery
        s = battery.status
        pct = s.get("percentage")
        if pct is not None:
            return "Energiestatus: %d procent." % int(pct)
    except Exception:
        pass
    return "Energiestatus: alle systemen optimaal."


# ===========================================================================
# Instellingen + server
# ===========================================================================
def _cfg_path():
    try:
        d = App.get_running_app().user_data_dir
    except Exception:
        d = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(d, "kitt_mobile.json")


def load_cfg():
    try:
        with open(_cfg_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(cfg):
    try:
        with open(_cfg_path(), "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass


def discover(on_found, on_none, timeout=3.0):
    """Zoek het hoofdkwartier op het thuisnetwerk (geen IP typen nodig)."""
    def work():
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.settimeout(timeout)
            for tgt in ("255.255.255.255", "<broadcast>"):
                try:
                    s.sendto(b"DRAVEKITT?", (tgt, 8001))
                except Exception:
                    pass
            data, _addr = s.recvfrom(1024)
            txt = data.decode("utf-8", "replace")
            if txt.startswith("DRAVEKITT|"):
                on_found(txt.split("|", 1)[1].strip())
                return
            on_none()
        except Exception:
            on_none()
        finally:
            try:
                s.close()
            except Exception:
                pass
    threading.Thread(target=work, daemon=True).start()


TOKEN = ""   # wachtwoord van de KITT-Server (leeg = geen)


def _hdr(extra=None):
    h = dict(extra or {})
    if TOKEN:
        h["X-Token"] = TOKEN
    return h


def ask_server(server, text, on_reply, on_fail):
    if not server:
        on_fail()
        return
    url = server.rstrip("/") + "/vraag"
    body = json.dumps({"text": text})
    headers = _hdr({"Content-type": "application/json", "Accept": "application/json"})

    def ok(req, result):
        reply = result.get("reply", "") if isinstance(result, dict) else ""
        on_reply(reply)

    def bad(req, *a):
        on_fail()

    try:
        UrlRequest(url, req_body=body, req_headers=headers, on_success=ok,
                   on_failure=bad, on_error=bad, timeout=20)
    except Exception:
        on_fail()


# ===========================================================================
# Voicebox: 3 kolommen rode (afgeronde) segmenten, gecentreerd
# ===========================================================================
class VoiceBox(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.phase = 0.0
        self.level = 0.0           # start STIL en ZWART; beweegt alleen als KITT praat
        self.active = False
        Clock.schedule_interval(self._tick, 1 / 30.0)
        self.bind(pos=lambda *a: self._draw(), size=lambda *a: self._draw())

    def _tick(self, dt):
        # alleen bewegen als KITT praat; anders rustig naar nul (stil en zwart)
        target = 1.0 if self.active else 0.0
        self.level += (target - self.level) * min(1.0, dt * 6.0)
        self.phase += dt * 6.0
        self._draw()

    def _draw(self):
        self.canvas.clear()
        # stil = helemaal zwart (niets tekenen) als KITT niet praat
        if self.width <= 0 or self.height <= 0 or self.level < 0.05:
            return
        cx = self.x + self.width / 2.0
        cy = self.y + self.height / 2.0          # MIDDENlijn: vanaf hier op en neer
        maxhalf = self.height / 2.0 - dp(4)
        colw = max(dp(10), self.width * 0.16)
        spacing = self.width * 0.30
        centers = [cx - spacing, cx, cx + spacing]
        pitch = max(dp(8), self.height / 16.0)
        segh = pitch * 0.6
        # GEDEELDE spraak-amplitude: alle kolommen gaan SAMEN met de stem mee op/neer
        amp = self.level * max(0.18, min(1.0, 0.45 + 0.55 * abs(
            0.7 * math.sin(self.phase * 2.0) + 0.3 * math.sin(self.phase * 3.3))))
        # zijkolommen volgen het midden maar blijven altijd lager (midden domineert)
        sidej = 0.80 + 0.18 * abs(math.sin(self.phase * 2.4))
        heights = [0.55 * amp * sidej, 1.0 * amp, 0.55 * amp * sidej]
        with self.canvas:
            for ci, cxx in enumerate(centers):
                colh = max(0.06, min(1.0, heights[ci]))
                halfpix = colh * maxhalf
                nseg = max(1, int(halfpix / pitch))
                for k in range(nseg + 1):
                    inten = max(0.45, 1.0 - (k / (nseg + 0.001)) * 0.5)
                    Color(0.32 + 0.68 * inten, 0.05 * inten, 0.03, 1)
                    # vanuit het midden OMHOOG
                    RoundedRectangle(pos=(cxx - colw / 2.0, cy + k * pitch),
                                     size=(colw, segh), radius=[dp(3)])
                    # en gespiegeld vanuit het midden OMLAAG
                    if k > 0:
                        RoundedRectangle(pos=(cxx - colw / 2.0, cy - k * pitch - segh),
                                         size=(colw, segh), radius=[dp(3)])


# ===========================================================================
# Afgeronde KITT-knop (amber/rood)
# ===========================================================================
class KittButton(Button):
    def __init__(self, face, **kw):
        super().__init__(background_normal="", background_color=(0, 0, 0, 0),
                         color=DARKTXT, bold=True, **kw)
        with self.canvas.before:
            self._col = Color(*face)
            self._rect = RoundedRectangle(radius=[dp(14)])
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *a):
        self._rect.pos = self.pos
        self._rect.size = self.size


# ===========================================================================
# Hoofd-UI
# ===========================================================================
class KittUI(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=dp(8), spacing=dp(6), **kw)
        cfg = load_cfg()
        self.server = cfg.get("server", "")
        global TOKEN
        TOKEN = (cfg.get("token") or "").strip()
        self.server_voice = cfg.get("server_voice", "")     # KITT-stem (neuvoice) op de pc
        self.server_speed = float(cfg.get("server_speed", 1.0) or 1.0)
        self.last_reply = ""
        self.pending = None
        self._snd = None

        # --- bovenbalk: logo + titel + Instellen ---
        top = BoxLayout(size_hint=(1, 0.09), spacing=dp(8))
        _logo = "logo_t.png" if os.path.exists("logo_t.png") else "logo.png"
        if os.path.exists(_logo):
            top.add_widget(Image(source=_logo, size_hint=(None, 1), width=dp(40)))
        top.add_widget(Label(text="DraveKITT", font_size=sp(24), bold=True,
                             color=(0.92, 0.92, 0.95, 1)))
        gear = Button(text="Instellen", size_hint=(None, 1), width=dp(110),
                      font_size=sp(15), background_normal="",
                      background_color=(0.2, 0.2, 0.24, 1), color=(0.9, 0.9, 0.92, 1))
        gear.bind(on_release=lambda *a: self._settings())
        # DraveKITT Mobile is gratis (donationware)
        don = Button(text="\u2665 Doneer", size_hint=(None, 1), width=dp(100),
                     font_size=sp(15), bold=True, background_normal="",
                     background_color=(0.36, 0.17, 0.53, 1), color=(1, 1, 1, 1))
        don.bind(on_release=lambda *a: _open_url("https://paypal.me/roger076"))
        top.add_widget(don)
        top.add_widget(gear)
        self.add_widget(top)

        # --- dashboard: links | voicebox | rechts ---
        dash = BoxLayout(size_hint=(1, 0.42), spacing=dp(6))
        left = BoxLayout(orientation="vertical", size_hint=(0.28, 1), spacing=dp(6))
        for lbl, face in LEFT_BTNS:
            left.add_widget(self._kbtn(lbl, face))
        dash.add_widget(left)
        self.voicebox = VoiceBox(size_hint=(0.44, 1))
        dash.add_widget(self.voicebox)
        right = BoxLayout(orientation="vertical", size_hint=(0.28, 1), spacing=dp(6))
        for lbl, face in RIGHT_BTNS:
            right.add_widget(self._kbtn(lbl, face))
        dash.add_widget(right)
        self.add_widget(dash)

        # --- antwoord ---
        self.answer = Label(text="Alle systemen online. Waarmee kan ik van dienst zijn?",
                            font_size=sp(18), color=(0.8, 0.85, 0.95, 1),
                            halign="center", valign="middle", size_hint=(1, 0.22))
        self.answer.size_hint = (1, 0.19)
        self.answer.bind(size=lambda *a: setattr(
            self.answer, "text_size", (self.answer.width - dp(16), None)))
        self.add_widget(self.answer)

        # --- invoer ---
        self.box = TextInput(hint_text="Typ je vraag...", multiline=False,
                             font_size=sp(18), size_hint=(1, 0.18),
                             background_color=(0.1, 0.1, 0.12, 1),
                             foreground_color=(0.9, 0.9, 0.92, 1),
                             cursor_color=(0.85, 0.2, 0.2, 1))
        self.box.bind(on_text_validate=lambda *a: self._ask(self.box.text))
        self.add_widget(self.box)

        # --- Vraag / Spreek (wat compacter) ---
        row = BoxLayout(size_hint=(1, 0.11), spacing=dp(10))
        vr = Button(text="Vraag", font_size=sp(18), bold=True, background_normal="",
                    background_color=(0.44, 0.64, 0.84, 1), color=DARKTXT)
        vr.bind(on_release=lambda *a: self._ask(self.box.text))
        row.add_widget(vr)
        sp_btn = Button(text="Spreek", font_size=sp(18), bold=True, background_normal="",
                        background_color=(0.7, 0.18, 0.16, 1), color=(1, 0.95, 0.95, 1))
        sp_btn.bind(on_release=lambda *a: self._listen())
        row.add_widget(sp_btn)
        self.add_widget(row)

    def _kbtn(self, label, face):
        b = KittButton(face, text=label, font_size=sp(14))
        b.bind(on_release=lambda *a: self._side(label))
        return b

    # ---- spreken/antwoorden ----
    def _say(self, reply, server_voice=False):
        self.last_reply = reply
        self.answer.text = reply
        self.voicebox.active = True
        if server_voice and self.server:
            self._speak_via_server(reply)   # echte KITT-stem (neuvoice) van de pc
        else:
            VOICE.speak(reply)              # Android-stem (offline terugval)
        Clock.unschedule(self._calm)
        Clock.schedule_once(self._calm, 6)

    def _speak_via_server(self, text):
        try:
            tmp = os.path.join(App.get_running_app().user_data_dir, "kitt_reply.wav")
        except Exception:
            tmp = "kitt_reply.wav"
        url = self.server.rstrip("/") + "/spreek"
        body = json.dumps({"text": text, "voice": self.server_voice,
                           "speed": self.server_speed})
        headers = _hdr({"Content-type": "application/json"})

        def ok(req, result):
            try:
                status = getattr(req, "resp_status", 200)
                if status == 204 or (not os.path.exists(tmp)) or os.path.getsize(tmp) < 100:
                    VOICE.speak(text)       # geen stem op de server -> Android
                    return
            except Exception:
                pass
            self._play_wav(tmp, text)

        def bad(req, *a):
            VOICE.speak(text)

        try:
            UrlRequest(url, req_body=body, req_headers=headers, on_success=ok,
                       on_failure=bad, on_error=bad, file_path=tmp, timeout=30)
        except Exception:
            VOICE.speak(text)

    def _play_wav(self, path, fallback_text=""):
        try:
            from kivy.core.audio import SoundLoader
            if getattr(self, "_snd", None):
                try:
                    self._snd.stop()
                except Exception:
                    pass
            self._snd = SoundLoader.load(path)
            if self._snd:
                self._snd.play()
            elif fallback_text:
                VOICE.speak(fallback_text)
        except Exception:
            if fallback_text:
                VOICE.speak(fallback_text)

    def _calm(self, *a):
        self.voicebox.active = False

    def _ask(self, text):
        text = (text or "").strip()
        if not text:
            return
        self.box.text = ""
        # wacht KITT op een plaats/bron (na WEER/NIEUWS)?
        if self.pending == "weer":
            self.pending = None
            text = "wat is het weer in %s" % text
        elif self.pending == "nieuws":
            self.pending = None
            text = "geef kort het nieuws over %s" % text
        if self.server:
            self.answer.text = "Even contact maken met het hoofdkwartier..."
            self.voicebox.active = True
            ask_server(self.server, text,
                       lambda r: self._say(r or kitt_reply(text), server_voice=True),
                       lambda: self._say(HQ_DOWN + "\n\n" + kitt_reply(text)))
        else:
            self._say(kitt_reply(text))

    def _listen(self):
        self.answer.text = "Luisteren..."
        self.voicebox.active = True
        android_listen(
            lambda txt: Clock.schedule_once(lambda dt: self._voice_done(txt), 0),
            lambda reden="": Clock.schedule_once(lambda dt: self._voice_fail(reden), 0))

    def _voice_done(self, txt):
        self.voicebox.active = False
        self.box.text = txt
        self._ask(txt)

    def _voice_fail(self, reden):
        self.voicebox.active = False
        self.answer.text = "Spraak lukt niet - typ je vraag.\n(reden: %s)" % (reden or "?")

    # ---- zijknoppen ----
    def _side(self, label):
        if label == "TIJD":
            self._say("Het is " + datetime.datetime.now().strftime("%H:%M") + " uur.")
        elif label == "ACCU":
            self._say(phone_battery())
        elif label == "SYSTEEM":
            self._say("Diagnose voltooid. Alle systemen functioneren naar behoren.")
        elif label == "GRAP":
            self._say(kitt_reply("grap"))
        elif label == "SCAN":
            self._say("Scan voltooid. Geen bedreigingen gedetecteerd.")
        elif label == "HULP":
            self._say("Vraag me naar de tijd, het weer of nieuws, of praat gewoon. "
                      "WEER en NIEUWS vragen eerst om een plaats of onderwerp.")
        elif label == "NIEUW":
            self.box.text = ""
            self._say("Nieuw gesprek. Ik luister.")
        elif label == "HERHAAL":
            if self.last_reply:
                self._say(self.last_reply)
            else:
                self._say("Ik heb nog niets gezegd om te herhalen.")
        elif label == "WEER":
            self.pending = "weer"
            self.answer.text = "Voor welke plaats wil je het weer? Typ of spreek het in."
        elif label == "NIEUWS":
            self.pending = "nieuws"
            self.answer.text = "Welk onderwerp of welke bron? Typ of spreek het in."

    # ---- instellingen ----
    def _settings(self):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        box.add_widget(Label(text="Hoofdkwartier (je pc):", size_hint=(1, None),
                             height=dp(28), font_size=sp(17), bold=True))
        # automatisch zoeken - geen IP typen nodig
        zoek = Button(text="Zoek hoofdkwartier (automatisch)", size_hint=(1, None),
                      height=dp(52), font_size=sp(17), bold=True, background_normal="",
                      background_color=(0.44, 0.64, 0.84, 1), color=DARKTXT)
        box.add_widget(zoek)
        # adresveld (groot, hoog contrast) + wis-knop
        arow = BoxLayout(size_hint=(1, None), height=dp(56), spacing=dp(8))
        field = TextInput(text=self.server, multiline=False, font_size=sp(20),
                          background_color=(0.12, 0.12, 0.15, 1),
                          foreground_color=(0.95, 0.95, 0.97, 1),
                          cursor_color=(0.85, 0.2, 0.2, 1),
                          hint_text="bv. http://192.168.1.50:8000",
                          hint_text_color=(0.55, 0.55, 0.6, 1))
        arow.add_widget(field)
        wis = Button(text="Wis", size_hint=(None, 1), width=dp(80), font_size=sp(17),
                     background_normal="", background_color=(0.5, 0.2, 0.18, 1),
                     color=(1, 0.95, 0.95, 1))
        wis.bind(on_release=lambda *a: setattr(field, "text", ""))
        arow.add_widget(wis)
        box.add_widget(arow)
        # wachtwoord (alleen nodig als je op de KITT-Server een wachtwoord hebt ingesteld)
        tok = TextInput(text=TOKEN, multiline=False, password=True, font_size=sp(18),
                        size_hint=(1, None), height=dp(48),
                        background_color=(0.12, 0.12, 0.15, 1),
                        foreground_color=(0.95, 0.95, 0.97, 1),
                        hint_text="wachtwoord van de server (leeg = geen)",
                        hint_text_color=(0.55, 0.55, 0.6, 1))
        box.add_widget(tok)

        # apart statusregeltje (zodat de knoptekst netjes blijft)
        status = Label(text="", size_hint=(1, None), height=dp(40),
                       font_size=sp(15), color=(0.7, 0.8, 0.95, 1), halign="center",
                       valign="middle")
        status.bind(size=lambda *a: setattr(status, "text_size",
                                            (status.width - dp(10), None)))
        box.add_widget(status)

        def _zoek(*a):
            status.text = "Zoeken op het netwerk..."

            def found(addr):
                def apply(dt):
                    field.text = addr
                    status.text = "Gevonden! Adres ingevuld. Klik Opslaan."
                Clock.schedule_once(apply, 0)

            def none():
                Clock.schedule_once(lambda dt: setattr(
                    status, "text",
                    "Niet gevonden. Staat de telefoon op wifi (niet 4G) en draait "
                    "de KITT-server?"), 0)
            discover(found, none)
        zoek.bind(on_release=_zoek)

        box.add_widget(Label(text="Spreeksnelheid", size_hint=(1, None), height=dp(22),
                             font_size=sp(15)))
        sl_rate = Slider(min=0.6, max=1.6, value=self.server_speed, size_hint=(1, None),
                         height=dp(40))
        box.add_widget(sl_rate)

        # KITT-stem van de pc (neuvoice) - opgehaald bij de server
        box.add_widget(Label(text="KITT-stem (van de pc)", size_hint=(1, None),
                             height=dp(24), font_size=sp(15)))
        spin = Spinner(text=(self.server_voice or "standaard"), values=["standaard"],
                       size_hint=(1, None), height=dp(48), font_size=sp(16))
        box.add_widget(spin)
        if self.server:
            def _got_voices(req, result):
                try:
                    vs = result.get("voices", []) if isinstance(result, dict) else []
                except Exception:
                    vs = []
                if vs:
                    spin.values = ["standaard"] + vs
                    if self.server_voice in vs:
                        spin.text = self.server_voice
            try:
                UrlRequest(self.server.rstrip("/") + "/stemmen", req_headers=_hdr(), on_success=_got_voices,
                           on_failure=lambda *a: None, on_error=lambda *a: None, timeout=8)
            except Exception:
                pass

        test = Button(text="Test stem", size_hint=(1, None), height=dp(44),
                      background_normal="", background_color=(0.3, 0.3, 0.36, 1))

        def _apply_voice():
            self.server_speed = sl_rate.value
            VOICE.rate = sl_rate.value
            self.server_voice = "" if spin.text == "standaard" else spin.text

        def _test(*a):
            _apply_voice()
            if self.server:
                self._speak_via_server("Hallo, dit is de gekozen KITT-stem.")
            else:
                VOICE.speak("Hallo, dit is de stem.")
        test.bind(on_release=_test)
        box.add_widget(test)

        row = BoxLayout(size_hint=(1, None), height=dp(48), spacing=dp(10))
        pop = Popup(title="Instellingen", content=box, size_hint=(0.92, 0.9))
        ok = Button(text="Opslaan", background_normal="",
                    background_color=(0.44, 0.64, 0.84, 1), color=DARKTXT)

        def _save(*a):
            global TOKEN
            self.server = field.text.strip()
            TOKEN = tok.text.strip()
            _apply_voice()
            save_cfg({"server": self.server, "server_voice": self.server_voice,
                      "server_speed": self.server_speed, "voice_name": VOICE.name,
                      "token": TOKEN})
            pop.dismiss()
            self._ping()
        ok.bind(on_release=_save)
        ann = Button(text="Annuleren", background_normal="",
                     background_color=(0.25, 0.25, 0.3, 1))
        ann.bind(on_release=lambda *a: pop.dismiss())
        row.add_widget(ann)
        row.add_widget(ok)
        box.add_widget(row)
        pop.open()

    def _ping(self):
        if not self.server:
            self.answer.text = ("Nog geen hoofdkwartier ingesteld - ik gebruik mijn "
                                "eigen lichte antwoorden. Klik 'Instellen'.")
            return
        self.answer.text = "Contact zoeken met het hoofdkwartier..."
        try:
            UrlRequest(self.server.rstrip("/") + "/ping", req_headers=_hdr(),
                       on_success=lambda r, x: setattr(
                           self.answer, "text",
                           "Verbonden met het hoofdkwartier. Ik sta tot je dienst."),
                       on_failure=lambda r, x: setattr(self.answer, "text", HQ_DOWN),
                       on_error=lambda r, x: setattr(self.answer, "text", HQ_DOWN),
                       timeout=8)
        except Exception:
            self.answer.text = HQ_DOWN


class DraveKITTApp(App):
    title = "DraveKITT"

    def build(self):
        try:
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.RECORD_AUDIO, Permission.INTERNET])
        except Exception:
            pass
        VOICE.init_android()
        cfg = load_cfg()
        VOICE.rate = float(cfg.get("voice_rate", 1.0) or 1.0)
        VOICE.pitch = float(cfg.get("voice_pitch", 1.0) or 1.0)
        VOICE.name = cfg.get("voice_name", "") or ""
        if not VOICE.name:
            VOICE.name = VOICE.default_dutch()    # standaard een NL-stem
        self.ui = KittUI()
        return self.ui

    def on_start(self):
        VOICE.speak("Alle systemen online.")
        # voicebox even laten meebewegen met de begroeting, daarna weer stil/zwart
        self.ui.voicebox.active = True
        Clock.schedule_once(self.ui._calm, 4)
        Clock.schedule_once(lambda *a: self.ui._ping(), 1.0)


if __name__ == "__main__":
    DraveKITTApp().run()
